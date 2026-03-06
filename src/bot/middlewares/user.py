from typing import Any, Awaitable, Callable, Optional
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.repositories.user import get_or_create_user


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, Update):
            if event.message and event.message.from_user:
                tg_user = event.message.from_user
            elif event.callback_query and event.callback_query.from_user:
                tg_user = event.callback_query.from_user

        if tg_user:
            session: AsyncSession = data["session"]
            # Extract ref parameter from /start if present
            referrer_id: Optional[int] = None
            if isinstance(event, Update) and event.message and event.message.text:
                text = event.message.text
                if text.startswith("/start ref_"):
                    try:
                        referrer_id = int(text.split("ref_")[1].strip())
                        if referrer_id == tg_user.id:
                            referrer_id = None
                    except (ValueError, IndexError):
                        referrer_id = None

            user, created = await get_or_create_user(
                user_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                referrer_id=referrer_id,
                session=session,
            )
            data["user"] = user
            data["is_new_user"] = created

        return await handler(event, data)
