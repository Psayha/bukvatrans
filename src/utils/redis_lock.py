from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as aioredis

from src.config import settings

_redis: Optional[aioredis.Redis] = None


def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


@asynccontextmanager
async def user_lock(user_id: int, timeout: int = 600):
    """Distributed lock per user_id to prevent concurrent transcriptions."""
    redis = get_redis()
    lock_key = f"lock:transcription:{user_id}"
    acquired = await redis.set(lock_key, "1", nx=True, ex=timeout)
    if not acquired:
        raise RuntimeError("Дождитесь завершения предыдущей задачи.")
    try:
        yield
    finally:
        await redis.delete(lock_key)
