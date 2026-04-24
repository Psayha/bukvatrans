from datetime import datetime

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
from src.db.models.subscription import Subscription
from src.db.models.transaction import Transaction
from src.db.models.transcription import Transcription
from src.db.models.user import User
from src.db.repositories.user import add_balance, get_user
from src.utils.formatters import format_balance
from src.utils.logging import get_logger

router = Router()
logger = get_logger(__name__)


# ---------- /admin_balance ----------

@router.message(Command("admin_balance"))
async def cmd_admin_balance(
    message: Message, user: User, session: AsyncSession
) -> None:
    if not await guard(user):
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Использование: /admin_balance USER_ID SECONDS")
        return
    try:
        target_id, seconds = int(parts[1]), int(parts[2])
    except ValueError:
        await message.answer("Неверные аргументы.")
        return

    await request_approval(
        message, user, "balance",
        args=[str(target_id), str(seconds)],
        human=f"balance {target_id} += {seconds}s",
    )


@register_approved("balance")
async def _execute_balance(
    message: Message, session: AsyncSession, requester_id: int, args: list[str]
) -> None:
    target_id, seconds = int(args[0]), int(args[1])
    target = await get_user(target_id, session)
    if not target:
        await message.answer(f"Пользователь {target_id} не найден.")
        return
    await add_balance(target_id, seconds, session)
    logger.info("admin_add_balance", admin_id=requester_id, target_id=target_id, seconds=seconds)
    await message.answer(f"✅ Добавлено {seconds} сек пользователю {target_id}.")


# ---------- /admin_ban, /admin_unban ----------

@router.message(Command("admin_ban"))
async def cmd_admin_ban(
    message: Message, user: User, session: AsyncSession
) -> None:
    await _toggle_ban(message, user, "ban")


@router.message(Command("admin_unban"))
async def cmd_admin_unban(
    message: Message, user: User, session: AsyncSession
) -> None:
    await _toggle_ban(message, user, "unban")


async def _toggle_ban(message: Message, user: User, action: str) -> None:
    if not await guard(user):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer(f"Использование: /admin_{action} USER_ID")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID.")
        return
    await request_approval(
        message, user, action, args=[str(target_id)], human=f"{action} {target_id}"
    )


@register_approved("ban")
async def _execute_ban(
    message: Message, session: AsyncSession, requester_id: int, args: list[str]
) -> None:
    await _set_ban(message, session, requester_id, int(args[0]), banned=True)


@register_approved("unban")
async def _execute_unban(
    message: Message, session: AsyncSession, requester_id: int, args: list[str]
) -> None:
    await _set_ban(message, session, requester_id, int(args[0]), banned=False)


async def _set_ban(
    message: Message,
    session: AsyncSession,
    requester_id: int,
    target_id: int,
    *,
    banned: bool,
) -> None:
    target = await get_user(target_id, session)
    if not target:
        await message.answer(f"Пользователь {target_id} не найден.")
        return
    target.is_banned = banned
    await session.commit()
    verb = "заблокирован" if banned else "разблокирован"
    emoji = "🚫" if banned else "✅"
    logger.info(
        "admin_set_ban", admin_id=requester_id, target_id=target_id, banned=banned
    )
    await message.answer(f"{emoji} Пользователь {target_id} {verb}.")


# ---------- /admin_user ----------

@router.message(Command("admin_user"))
async def cmd_admin_user(
    message: Message, user: User, session: AsyncSession
) -> None:
    if not await guard(user):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /admin_user USER_ID")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID.")
        return

    target = await get_user(target_id, session)
    if not target:
        await message.answer(f"Пользователь {target_id} не найден.")
        return

    # Aggregate side info in parallel-ish (serial but cheap).
    total_trans = await session.scalar(
        select(func.count(Transcription.id)).where(Transcription.user_id == target_id)
    ) or 0
    done_trans = await session.scalar(
        select(func.count(Transcription.id)).where(
            Transcription.user_id == target_id,
            Transcription.status == "done",
        )
    ) or 0
    total_paid = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount_rub), 0)).where(
            Transaction.user_id == target_id,
            Transaction.status == "success",
            Transaction.type.in_(["subscription", "topup"]),
        )
    ) or 0
    referrals_count = await session.scalar(
        select(func.count(User.id)).where(User.referrer_id == target_id)
    ) or 0

    # Active subscription, if any.
    sub_result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == target_id,
            Subscription.status == "active",
            Subscription.expires_at > datetime.utcnow(),
        )
        .order_by(Subscription.expires_at.desc())
        .limit(1)
    )
    sub = sub_result.scalar_one_or_none()
    sub_line = (
        f"{sub.plan} до {sub.expires_at:%d.%m.%Y}" if sub else "нет"
    )

    username = f"@{target.username}" if target.username else "—"
    name = " ".join(p for p in [target.first_name, target.last_name] if p) or "—"
    email = target.email or "—"
    referrer = f"<code>{target.referrer_id}</code>" if target.referrer_id else "—"

    text = (
        f"👤 <b>Пользователь {target_id}</b>\n\n"
        f"Имя: {name}\n"
        f"Username: {username}\n"
        f"Email: {email}\n"
        f"Регистрация: {target.created_at:%d.%m.%Y %H:%M}\n"
        f"Бан: {'🚫 да' if target.is_banned else '✅ нет'}\n\n"
        f"💰 Баланс: <b>{format_balance(target.balance_seconds)}</b>\n"
        f"🎁 Бесплатных попыток: <b>{target.free_uses_left}</b>\n"
        f"📅 Подписка: {sub_line}\n\n"
        f"🎙 Транскрибаций всего: {total_trans} (успешных {done_trans})\n"
        f"💳 Оплачено всего: <b>{float(total_paid):,.2f} ₽</b>\n"
        f"🔗 Приглашённых: {referrals_count}\n"
        f"👤 Реферер: {referrer}"
    )
    await message.answer(text, parse_mode="HTML")
