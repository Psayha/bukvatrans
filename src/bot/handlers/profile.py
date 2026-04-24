from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.texts.ru import HISTORY_EMPTY, NO_SUBSCRIPTION, PROFILE_TEXT
from src.db.models.transcription import Transcription
from src.db.models.user import User
from src.db.repositories.transcription import get_user_transcriptions
from src.services.billing import PLANS
from src.utils.formatters import format_balance, format_duration
from src.utils.gamification import format_level_line, saved_time_phrase

router = Router()


@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User, session: AsyncSession) -> None:
    recent = await get_user_transcriptions(user.id, session, limit=100)
    total_transcriptions = len(recent)

    total_audio_seconds = await session.scalar(
        select(func.coalesce(func.sum(Transcription.duration_seconds), 0)).where(
            Transcription.user_id == user.id,
            Transcription.status == "done",
        )
    ) or 0

    subscription = NO_SUBSCRIPTION
    if user.has_active_subscription():
        for sub in user.subscriptions:
            if sub.status == "active" and sub.expires_at > datetime.now(timezone.utc):
                plan_label = PLANS.get(sub.plan, {}).get("label", sub.plan)
                subscription = f"{plan_label} до {sub.expires_at:%d.%m.%Y}"
                break

    ref_link = f"https://t.me/{(await message.bot.get_me()).username}?start=ref_{user.id}"

    text = PROFILE_TEXT.format(
        user_id=user.id,
        level_line=format_level_line(total_audio_seconds),
        balance=format_balance(user.balance_seconds),
        free_uses=user.free_uses_left,
        subscription=subscription,
        total_transcriptions=total_transcriptions,
        total_audio=format_duration(total_audio_seconds),
        ai_dialogs=user.ai_dialogs_count,
        saved_time=saved_time_phrase(total_audio_seconds),
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
