"""Admin commands gated by two-admin approval.

Every mutating command (and read-only /admin_stats, which leaks user counts)
goes through `utils.admin_approval`: the first admin issues the command, the
bot fans out an approval request to the *other* admins, and a different admin
must click Approve before the action executes.

A single-admin deployment can skip 2FA by listing only one admin id — in that
case the approval step is a no-op.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models.transaction import Transaction
from src.db.models.transcription import Transcription
from src.db.models.user import User
from src.db.repositories.user import add_balance, get_user
from src.services.notification import send_message
from src.utils import admin_approval, ratelimit
from src.utils.logging import get_logger

router = Router()
logger = get_logger(__name__)

# Hard ceiling on wrong-user admin-command attempts: 3 per 15 min.
_ADMIN_PROBE_LIMIT = 3
_ADMIN_PROBE_WINDOW = 900


def is_admin(user: User) -> bool:
    return user.is_admin or user.id in settings.admin_ids_list


async def _guard(user: User) -> bool:
    if is_admin(user):
        return True
    allowed, count = await ratelimit.hit(
        f"admin:probe:{user.id}", _ADMIN_PROBE_LIMIT, _ADMIN_PROBE_WINDOW
    )
    if not allowed:
        logger.warning("admin_probe_threshold", user_id=user.id, count=count)
    return False


def _other_admin_ids(requester_id: int) -> list[int]:
    return [aid for aid in settings.admin_ids_list if aid != requester_id]


def _approval_kb(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_ok:{token}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_no:{token}"),
            ]
        ]
    )


async def _request_approval(
    message: Message, requester: User, command: str, args: list[str], human: str
) -> None:
    """Create a pending approval and DM the other admins.

    If the deployment has only one admin, execute immediately (2FA-skipped).
    """
    other_ids = _other_admin_ids(requester.id)
    if not other_ids:
        # Solo-admin deployment — no peer to approve. Execute inline to avoid
        # locking the owner out of their own bot.
        logger.info("admin_solo_execute", admin_id=requester.id, command=command)
        await _execute(message, requester.id, command, args)
        return

    token = await admin_approval.create(requester.id, command, args)
    text = (
        f"🛡 <b>Админ-подтверждение</b>\n\n"
        f"Запросил: <code>{requester.id}</code>\n"
        f"Действие: <code>{human}</code>\n\n"
        f"Истекает через {settings.ADMIN_APPROVAL_TTL_SECONDS // 60} мин."
    )
    for aid in other_ids:
        try:
            await send_message(
                aid, text, parse_mode="HTML", reply_markup=_approval_kb(token).model_dump(by_alias=True)
            )
        except Exception:
            logger.warning("admin_approval_dm_failed", admin_id=aid, exc_info=True)
    await message.answer(
        f"🕐 Ожидаю подтверждение от второго админа (≤ {settings.ADMIN_APPROVAL_TTL_SECONDS // 60} мин).",
    )


async def _execute(
    message: Message, requester_id: int, command: str, args: list[str]
) -> None:
    """Run the approved command. A fresh DB session is opened here because
    the original handler's session may have already been closed (approval
    can arrive minutes later)."""
    from src.db.base import async_session_factory

    async with async_session_factory() as session:
        if command == "balance":
            target_id, seconds = int(args[0]), int(args[1])
            target = await get_user(target_id, session)
            if not target:
                await message.answer(f"Пользователь {target_id} не найден.")
                return
            await add_balance(target_id, seconds, session)
            logger.info(
                "admin_add_balance", admin_id=requester_id, target_id=target_id, seconds=seconds
            )
            await message.answer(f"✅ Добавлено {seconds} сек пользователю {target_id}.")

        elif command in ("ban", "unban"):
            target_id = int(args[0])
            target = await get_user(target_id, session)
            if not target:
                await message.answer(f"Пользователь {target_id} не найден.")
                return
            target.is_banned = command == "ban"
            await session.commit()
            logger.info(f"admin_{command}", admin_id=requester_id, target_id=target_id)
            verb = "заблокирован" if command == "ban" else "разблокирован"
            emoji = "🚫" if command == "ban" else "✅"
            await message.answer(f"{emoji} Пользователь {target_id} {verb}.")

        elif command == "stats":
            text = await _build_stats_text(session)
            await message.answer(text, parse_mode="HTML")


async def _build_stats_text(session: AsyncSession) -> str:
    day_ago = datetime.utcnow() - timedelta(days=1)
    week_ago = datetime.utcnow() - timedelta(days=7)

    total_users = await session.scalar(select(func.count(User.id))) or 0
    banned_users = await session.scalar(
        select(func.count(User.id)).where(User.is_banned.is_(True))
    ) or 0
    new_24h = await session.scalar(
        select(func.count(User.id)).where(User.created_at >= day_ago)
    ) or 0
    new_7d = await session.scalar(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    ) or 0

    done_24h = await session.scalar(
        select(func.count(Transcription.id)).where(
            Transcription.status == "done",
            Transcription.created_at >= day_ago,
        )
    ) or 0
    failed_24h = await session.scalar(
        select(func.count(Transcription.id)).where(
            Transcription.status == "failed",
            Transcription.created_at >= day_ago,
        )
    ) or 0
    hours_24h = (await session.scalar(
        select(func.sum(Transcription.duration_seconds)).where(
            Transcription.status == "done",
            Transcription.created_at >= day_ago,
        )
    ) or 0) // 3600

    pay_count_24h = await session.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.status == "success",
            Transaction.type.in_(["subscription", "topup"]),
            Transaction.created_at >= day_ago,
        )
    ) or 0
    pay_sum_24h = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount_rub), 0)).where(
            Transaction.status == "success",
            Transaction.type.in_(["subscription", "topup"]),
            Transaction.created_at >= day_ago,
        )
    ) or 0

    return (
        "📊 <b>Статистика</b>\n\n"
        f"👤 Пользователей: <b>{total_users}</b> (забанены: {banned_users})\n"
        f"🆕 Новых за 24ч: <b>{new_24h}</b>, за 7д: <b>{new_7d}</b>\n\n"
        f"🎙 Транскрибаций 24ч: <b>{done_24h}</b>, ошибок: <b>{failed_24h}</b>\n"
        f"⏱ Часов озвучки 24ч: <b>{hours_24h}</b>\n\n"
        f"💳 Оплат 24ч: <b>{pay_count_24h}</b> на <b>{float(pay_sum_24h):,.0f}₽</b>\n"
    )


# ---------- entry points ----------

@router.message(Command("admin"))
async def cmd_admin(message: Message, user: User, state: FSMContext) -> None:
    if not await _guard(user):
        return
    await message.answer(
        "🛠 <b>Админ-панель</b>\n\n"
        "/admin_balance USER_ID SECONDS — добавить баланс (2FA)\n"
        "/admin_ban USER_ID — забанить (2FA)\n"
        "/admin_unban USER_ID — разбанить (2FA)\n"
        "/admin_stats — статистика (2FA)",
        parse_mode="HTML",
    )


@router.message(Command("admin_balance"))
async def cmd_admin_balance(
    message: Message, user: User, session: AsyncSession
) -> None:
    if not await _guard(user):
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

    await _request_approval(
        message, user, "balance",
        args=[str(target_id), str(seconds)],
        human=f"balance {target_id} += {seconds}s",
    )


@router.message(Command("admin_ban"))
async def cmd_admin_ban(
    message: Message, user: User, session: AsyncSession
) -> None:
    if not await _guard(user):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /admin_ban USER_ID")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID.")
        return
    await _request_approval(
        message, user, "ban", args=[str(target_id)], human=f"ban {target_id}"
    )


@router.message(Command("admin_unban"))
async def cmd_admin_unban(
    message: Message, user: User, session: AsyncSession
) -> None:
    if not await _guard(user):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /admin_unban USER_ID")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID.")
        return
    await _request_approval(
        message, user, "unban", args=[str(target_id)], human=f"unban {target_id}"
    )


@router.message(Command("admin_stats"))
async def cmd_admin_stats(
    message: Message, user: User, session: AsyncSession
) -> None:
    if not await _guard(user):
        return
    await _request_approval(
        message, user, "stats", args=[], human="stats snapshot"
    )


# ---------- approval callbacks ----------

@router.callback_query(F.data.startswith("admin_ok:"))
async def cb_admin_approve(callback: CallbackQuery, user: User) -> None:
    if not is_admin(user):
        await callback.answer("Только для админов.", show_alert=True)
        return
    token = callback.data.split(":", 1)[1]
    req = await admin_approval.consume(token, approver_id=user.id)
    if req is None:
        await callback.answer("Запрос не найден, истёк или нельзя одобрить свой же.", show_alert=True)
        return

    await callback.message.edit_text(
        f"✅ Одобрено админом <code>{user.id}</code>. Выполняю…", parse_mode="HTML"
    )
    await _execute(callback.message, req.requester_id, req.command, req.args)
    # Tell the requester too.
    try:
        await send_message(
            req.requester_id,
            f"✅ Действие <code>{req.command} {' '.join(req.args)}</code> одобрено.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("admin_no:"))
async def cb_admin_deny(callback: CallbackQuery, user: User) -> None:
    if not is_admin(user):
        await callback.answer("Только для админов.", show_alert=True)
        return
    token = callback.data.split(":", 1)[1]
    req = await admin_approval.consume(token, approver_id=user.id)
    if req is None:
        await callback.answer("Запрос не найден или истёк.", show_alert=True)
        return
    await callback.message.edit_text(
        f"❌ Отклонено админом <code>{user.id}</code>.", parse_mode="HTML"
    )
    try:
        await send_message(
            req.requester_id,
            f"❌ Действие <code>{req.command} {' '.join(req.args)}</code> отклонено.",
            parse_mode="HTML",
        )
    except Exception:
        pass
    await callback.answer()
