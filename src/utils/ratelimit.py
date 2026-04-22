"""Small Redis-backed sliding counters for anti-brute-force and abuse limits.

Failures to reach Redis are treated as "allowed" — we would rather let a
request through than page the on-call because the counter service is down.
"""
from typing import Optional

import redis.asyncio as aioredis

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

_clients: dict[str, aioredis.Redis] = {}


def _client(url: Optional[str] = None) -> aioredis.Redis:
    key = url or settings.redis_ratelimit_url
    if key not in _clients:
        _clients[key] = aioredis.from_url(key, decode_responses=True)
    return _clients[key]


async def hit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    """Increment `key` and return (allowed, current_count).

    Fails open: on Redis error, return (True, 0) and log.
    """
    try:
        r = _client()
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, window_seconds)
        return (count <= limit, count)
    except Exception as e:
        logger.warning("ratelimit_unavailable", key=key, error=str(e))
        return (True, 0)


async def reset(key: str) -> None:
    try:
        r = _client()
        await r.delete(key)
    except Exception as e:
        logger.warning("ratelimit_reset_failed", key=key, error=str(e))
