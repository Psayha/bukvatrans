from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.handlers.admin._common import (
    guard,
    register_approved,
    request_approval,
)
from src.db.models.transaction import Transaction
from src.db.models.transcription import Transcription
from src.db.models.user import User

router = Router()


@router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message, user: User, session: AsyncSession) -> None:
    if not await guard(user):
        return
    await request_approval(message, user, "stats", args=[], human="stats snapshot")


@register_approved("stats")
async def _execute_stats(
    message: Message, session: AsyncSession, requester_id: int, args: list[str]
) -> None:
    text = await _build_stats_text(session)
    await message.answer(text, parse_mode="HTML")


async def _build_stats_text(session: AsyncSession) -> str:
    day_ago = datetime.utcnow() - timedelta(days=1)
    week_ago = datetime.utcnow() - timedelta(days=7)

    async def count(stmt) -> int:
        return (await session.scalar(stmt)) or 0

    total = await count(select(func.count(User.id)))
    banned = await count(
        select(func.count(User.id)).where(User.is_banned.is_(True))
    )
    new_24h = await count(
        select(func.count(User.id)).where(User.created_at >= day_ago)
    )
    new_7d = await count(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    )
    done_24h = await count(
        select(func.count(Transcription.id)).where(
            Transcription.status == "done",
            Transcription.created_at >= day_ago,
        )
    )
    failed_24h = await count(
        select(func.count(Transcription.id)).where(
            Transcription.status == "failed",
            Transcription.created_at >= day_ago,
        )
    )
    hours_24h = (
        await count(
            select(func.sum(Transcription.duration_seconds)).where(
                Transcription.status == "done",
                Transcription.created_at >= day_ago,
            )
        )
    ) // 3600
    pay_count_24h = await count(
        select(func.count(Transaction.id)).where(
            Transaction.status == "success",
            Transaction.type.in_(["subscription", "topup"]),
            Transaction.created_at >= day_ago,
        )
    )
    pay_sum_24h = await count(
        select(func.coalesce(func.sum(Transaction.amount_rub), 0)).where(
            Transaction.status == "success",
            Transaction.type.in_(["subscription", "topup"]),
            Transaction.created_at >= day_ago,
        )
    )

    return (
        "📊 <b>Статистика</b>\n\n"
        f"👤 Пользователей: <b>{total}</b> (забанены: {banned})\n"
        f"🆕 Новых за 24ч: <b>{new_24h}</b>, за 7д: <b>{new_7d}</b>\n\n"
        f"🎙 Транскрибаций 24ч: <b>{done_24h}</b>, ошибок: <b>{failed_24h}</b>\n"
        f"⏱ Часов озвучки 24ч: <b>{hours_24h}</b>\n\n"
        f"💳 Оплат 24ч: <b>{pay_count_24h}</b> на <b>{float(pay_sum_24h):,.0f}₽</b>\n"
    )
