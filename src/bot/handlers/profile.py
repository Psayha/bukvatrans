from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User
from src.db.repositories.transcription import get_user_transcriptions
from src.bot.texts.ru import (
    PROFILE_TEXT, HISTORY_EMPTY, HISTORY_ITEM, NO_SUBSCRIPTION
)
from src.utils.formatters import format_balance, format_duration
from src.config import settings

router = Router()


@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User, session: AsyncSession) -> None:
    total = len(await get_user_transcriptions(user.id, session, limit=100))

    subscription = NO_SUBSCRIPTION
    if user.has_active_subscription():
        for sub in user.subscriptions:
            from datetime import datetime
            if sub.status == "active" and sub.expires_at > datetime.utcnow():
                plan_names = {
                    "basic": "Базовый",
                    "pro": "Про (Безлимит)",
                }
                subscription = (
                    f"{plan_names.get(sub.plan, sub.plan)} до "
                    f"{sub.expires_at.strftime('%d.%m.%Y')}"
                )
                break

    ref_link = f"https://t.me/{(await message.bot.get_me()).username}?start=ref_{user.id}"

    text = PROFILE_TEXT.format(
        user_id=user.id,
        balance=format_balance(user.balance_seconds),
        free_uses=user.free_uses_left,
        total_transcriptions=total,
        subscription=subscription,
        ref_link=ref_link,
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("balance"))
async def cmd_balance(message: Message, user: User) -> None:
    await message.answer(
        f"💰 <b>Ваш баланс:</b> {format_balance(user.balance_seconds)}\n"
        f"🎁 Бесплатных попыток: <b>{user.free_uses_left}</b>",
        parse_mode="HTML",
    )


@router.message(Command("history"))
async def cmd_history(message: Message, user: User, session: AsyncSession) -> None:
    transcriptions = await get_user_transcriptions(user.id, session, limit=10)
    if not transcriptions:
        await message.answer(HISTORY_EMPTY)
        return

    STATUS_EMOJI = {
        "done": "✅",
        "failed": "❌",
        "processing": "⏳",
        "pending": "🕐",
        "cancelled": "🚫",
    }
    lines = ["<b>Последние транскрибации:</b>\n"]
    for idx, t in enumerate(transcriptions, 1):
        emoji = STATUS_EMOJI.get(t.status, "❓")
        duration = format_duration(t.duration_seconds) if t.duration_seconds else "—"
        date = t.created_at.strftime("%d.%m %H:%M")
        lines.append(f"{idx}. {date} — {duration} {emoji}")

    await message.answer("\n".join(lines), parse_mode="HTML")
