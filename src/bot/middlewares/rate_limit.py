from typing import Any, Awaitable, Callable

import redis.asyncio as aioredis
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from src.bot.texts.ru import RATE_LIMIT
from src.config import settings

RATE_LIMITS = {
    "commands": {"calls": 30, "period": 60},
}

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_ratelimit_url, decode_responses=True)
    return _redis


class RateLimitMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        if not user:
            return await handler(event, data)

        redis = _get_redis()
        key = f"rate:commands:{user.id}"
        limit = RATE_LIMITS["commands"]

        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, limit["period"])

        if count > limit["calls"]:
            if isinstance(event, Message):
                await event.answer(RATE_LIMIT)
            return

        return await handler(event, data)
