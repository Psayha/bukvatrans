"""Route around 152-ФЗ consent for users who haven't accepted yet.

Placed AFTER UserMiddleware so `data["user"]` is populated. If the user
hasn't clicked "Согласен" on their first /start, we intercept any message
that would trigger transcription / payment flows and re-show the consent
prompt instead.

Always-allowed commands / events: /start, /help, /privacy, /terms, /about,
/support, /cancel, and the consent callback itself. Everything else —
media, links, payments — gets the prompt.
"""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from src.bot.texts.ru import CONSENT_PROMPT
from src.db.models.user import User

# Messages with these commands bypass the consent gate.
_ALLOWED_COMMANDS = {
    "/start", "/help", "/privacy", "/terms", "/about",
    "/support", "/cancel", "/menu",
}

# Callback prefixes that must always work (accepting the consent itself).
_ALLOWED_CALLBACK_PREFIXES = ("consent:",)


class ConsentMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("user")
        if user is None or user.consent_at is not None:
            return await handler(event, data)

        # Unwrap the Update envelope so we can inspect what was sent.
        msg: Message | None = None
        cb: CallbackQuery | None = None
        if isinstance(event, Update):
            msg = event.message
            cb = event.callback_query

        if msg is not None:
            text = (msg.text or "").strip().split()
            first = text[0] if text else ""
            if first in _ALLOWED_COMMANDS:
                return await handler(event, data)
            # Any other message: gently redirect.
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

            from src.bot.texts.ru import CONSENT_BUTTON
            kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(
                    text=CONSENT_BUTTON, callback_data="consent:accept",
                )]],
            )
            await msg.answer(CONSENT_PROMPT, reply_markup=kb, parse_mode="HTML")
            return

        if cb is not None:
            cb_data = cb.data or ""
            if any(cb_data.startswith(p) for p in _ALLOWED_CALLBACK_PREFIXES):
                return await handler(event, data)
            await cb.answer("Сначала примите соглашение в /start", show_alert=True)
            return

        # Unknown event type — pass through.
        return await handler(event, data)
