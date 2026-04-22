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
    from datetime import timedelta
    from sqlalchemy import update
    from src.config import settings
    from src.db.base import async_session_factory
    from src.db.models.transcription import Transcription

    cutoff = datetime.utcnow() - timedelta(days=settings.TRANSCRIPTION_RETENTION_DAYS)

    async with async_session_factory() as session:
        result = await session.execute(
            update(Transcription)
            .where(
                Transcription.completed_at < cutoff,
                # Only touch rows that still carry text. Avoids churning
                # millions of already-purged rows on every sweep.
                (Transcription.result_text.isnot(None))
                | (Transcription.summary_text.isnot(None)),
            )
            .values(result_text=None, summary_text=None)
        )
        await session.commit()
    logger.info("purged_transcription_text rows=%s cutoff=%s", result.rowcount, cutoff)


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
