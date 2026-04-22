from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from src.bot.texts.ru import RATE_LIMIT
from src.utils import ratelimit

RATE_LIMITS = {
    "commands": {"calls": 30, "period": 60},
}


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

        limit = RATE_LIMITS["commands"]
        # `ratelimit.hit` fails open — a transient Redis outage lets the
        # request through instead of blocking every user in the bot.
        allowed, _ = await ratelimit.hit(
            f"rate:commands:{user.id}", limit["calls"], limit["period"]
        )
        if not allowed:
            if isinstance(event, Message):
                await event.answer(RATE_LIMIT)
            return

        return await handler(event, data)
