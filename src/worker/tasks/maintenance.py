import asyncio
import tempfile
from datetime import datetime
from pathlib import Path

from celery.utils.log import get_task_logger

from src.worker.app import app

logger = get_task_logger(__name__)


@app.task(name="src.worker.tasks.maintenance.expire_subscriptions")
def expire_subscriptions():
    asyncio.get_event_loop().run_until_complete(_expire_subscriptions())


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


@app.task(name="src.worker.tasks.maintenance.check_dead_letter_queue")
def check_dead_letter_queue():
    asyncio.get_event_loop().run_until_complete(_check_dlq())


async def _check_dlq():
    import redis.asyncio as aioredis
    from src.config import settings

    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    count = await redis.llen("celery_dlq")
    if count > 5:
        logger.warning(f"DLQ has {count} messages!")
        # Send alert to admin
        for admin_id in settings.admin_ids_list:
            from src.services.notification import send_message
            await send_message(admin_id, f"⚠️ DLQ: {count} мёртвых задач!")
