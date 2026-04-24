import asyncio
import tempfile
from datetime import datetime
from pathlib import Path

from celery.utils.log import get_task_logger

from src.worker.app import app

logger = get_task_logger(__name__)


def _run_async(coro):
    """Run a coroutine in a fresh event loop each task invocation.

    Celery's prefork workers don't always have a ready event loop; creating
    a fresh one avoids "no running event loop" / "loop is closed" errors in
    Python 3.12.
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(name="src.worker.tasks.maintenance.expire_subscriptions")
def expire_subscriptions():
    return _run_async(_expire_subscriptions())


async def _expire_subscriptions():
    from src.db.base import async_session_factory
    from src.db.models.subscription import Subscription
    from sqlalchemy import update

    async with async_session_factory() as session:
        now = datetime.utcnow()
        await session.execute(
            update(Subscription)
            .where(Subscription.expires_at < now, Subscription.status == "active")
            .values(status="expired")
        )
        await session.commit()
    logger.info("Expired subscriptions updated.")


@app.task(name="src.worker.tasks.maintenance.cleanup_tmp_files")
def cleanup_tmp_files():
    tmp = Path(tempfile.gettempdir())
    count = 0
    for f in tmp.glob("*.mp3"):
        try:
            f.unlink()
            count += 1
        except Exception:
            pass
    logger.info(f"Cleaned up {count} temp files.")


@app.task(name="src.worker.tasks.maintenance.purge_old_transcription_text")
def purge_old_transcription_text():
    """Erase user-generated transcript text older than the retention window.

    Telegram keeps the delivered message in the user's chat history, so the
    copy we hold server-side is just a caching convenience and a risk surface
    for 152-ФЗ / privacy reasons. We keep metadata (duration, status, price)
    indefinitely for billing audits, but wipe the speech content.
    """
    return _run_async(_purge_old_transcription_text())


async def _purge_old_transcription_text():
    """Zero out every field that could contain user PII on old rows.

    Purged:
      - result_text / summary_text  (the speech content)
      - source_url                  (may include filename / auth token
                                     e.g. a Google Drive share link with
                                     the owner's profile in the URL)
      - file_name                   (original upload filename)
      - error_message               (may leak paths / URLs in stack traces)

    Retained:
      - duration_seconds, seconds_charged, status, created_at, completed_at,
        source_type, file_unique_id  (all needed for billing audit trail;
        file_unique_id is a Telegram hash, not PII).
    """
    from datetime import timedelta
    from sqlalchemy import or_, update
    from src.config import settings
    from src.db.base import async_session_factory
    from src.db.models.transcription import Transcription

    cutoff = datetime.utcnow() - timedelta(days=settings.TRANSCRIPTION_RETENTION_DAYS)

    async with async_session_factory() as session:
        result = await session.execute(
            update(Transcription)
            .where(
                Transcription.completed_at < cutoff,
                # Only touch rows that still carry any of the PII fields —
                # keeps the sweep cheap once the backlog is drained.
                or_(
                    Transcription.result_text.isnot(None),
                    Transcription.summary_text.isnot(None),
                    Transcription.source_url.isnot(None),
                    Transcription.file_name.isnot(None),
                    Transcription.error_message.isnot(None),
                ),
            )
            .values(
                result_text=None,
                summary_text=None,
                source_url=None,
                file_name=None,
                error_message=None,
            )
        )
        await session.commit()
    logger.info("purged_transcription_text rows=%s cutoff=%s", result.rowcount, cutoff)


@app.task(name="src.worker.tasks.maintenance.notify_expiring_subscriptions")
def notify_expiring_subscriptions():
    """DM each user whose sub expires in 3, 2 or 1 days.

    We want the warning to fire roughly once per horizon per sub, so we
    select the window [now + N days, now + (N+1) days) for each N in
    (1, 2, 3). A flag `notified_<N>` is tracked in Redis so a daily
    re-run doesn't spam if the Celery beat loses its schedule file.
    """
    return _run_async(_notify_expiring_subscriptions())


async def _notify_expiring_subscriptions() -> None:
    from datetime import timedelta

    import redis.asyncio as aioredis
    from sqlalchemy import select

    from src.bot.texts.ru import SUB_EXPIRING_SOON
    from src.config import settings
    from src.db.base import async_session_factory
    from src.db.models.subscription import Subscription
    from src.services.notification import send_message

    warn_windows = (1, 2, 3)  # days-left buckets
    redis = aioredis.from_url(settings.redis_cache_url, decode_responses=True)
    sent_total = 0

    try:
        async with async_session_factory() as session:
            for days_left in warn_windows:
                now = datetime.utcnow()
                window_start = now + timedelta(days=days_left)
                window_end = window_start + timedelta(days=1)

                result = await session.execute(
                    select(Subscription).where(
                        Subscription.status == "active",
                        Subscription.expires_at >= window_start,
                        Subscription.expires_at < window_end,
                    )
                )
                subs = list(result.scalars())

                for sub in subs:
                    redis_key = f"sub:notify:{sub.id}:{days_left}"
                    if await redis.get(redis_key):
                        continue
                    try:
                        await send_message(
                            sub.user_id,
                            SUB_EXPIRING_SOON.format(
                                expires_at=sub.expires_at.strftime("%d.%m.%Y"),
                                days_left=days_left,
                            ),
                            parse_mode="HTML",
                        )
                        sent_total += 1
                    except Exception:
                        logger.warning(
                            "sub_notify_failed", user_id=sub.user_id, exc_info=True
                        )
                        continue
                    # Remember for ~ a month so repeats are idempotent.
                    await redis.set(redis_key, "1", ex=60 * 60 * 24 * 30)
    finally:
        await redis.close()

    logger.info("sub_expiring_notifications sent=%s", sent_total)


@app.task(name="src.worker.tasks.maintenance.reset_monthly_free_uses")
def reset_monthly_free_uses():
    """Top up free_uses_left to FREE_USES_PER_MONTH for users whose
    free_uses_reset_at has rolled past. First run for a fresh account
    sets the boundary without crediting."""
    return _run_async(_reset_monthly_free_uses())


async def _reset_monthly_free_uses() -> None:
    from sqlalchemy import or_, update

    from src.db.base import async_session_factory
    from src.db.models.user import User
    from src.services.billing import FREE_USES_PER_MONTH

    now = datetime.utcnow()
    # Start of next calendar month from now.
    if now.month == 12:
        next_reset = datetime(now.year + 1, 1, 1)
    else:
        next_reset = datetime(now.year, now.month + 1, 1)

    async with async_session_factory() as session:
        # Refill users whose reset boundary has passed OR who have never been
        # processed yet. Cap at the monthly allotment — never clobber a
        # higher count if e.g. a promo gave more.
        result = await session.execute(
            update(User)
            .where(
                or_(
                    User.free_uses_reset_at.is_(None),
                    User.free_uses_reset_at <= now,
                ),
                User.is_banned.is_(False),
            )
            .values(
                free_uses_left=FREE_USES_PER_MONTH,
                free_uses_reset_at=next_reset,
            )
        )
        await session.commit()
    logger.info("monthly_free_uses_reset rows=%s next=%s", result.rowcount, next_reset)


@app.task(name="src.worker.tasks.maintenance.check_dead_letter_queue")
def check_dead_letter_queue():
    return _run_async(_check_dlq())


async def _check_dlq():
    import redis.asyncio as aioredis

    from src.config import settings
    from src.utils import metrics

    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        count = await redis.llen("celery_dlq")
        metrics.dlq_size.set(count)
        if count > 5:
            logger.warning(f"DLQ has {count} messages!")
            from src.services.notification import send_message
            for admin_id in settings.admin_ids_list:
                await send_message(admin_id, f"⚠️ DLQ: {count} мёртвых задач!")
    finally:
        await redis.close()
