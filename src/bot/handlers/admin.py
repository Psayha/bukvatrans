from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models.transaction import Transaction
from src.db.models.transcription import Transcription
from src.db.models.user import User
from src.db.repositories.user import add_balance, get_user
from src.utils import ratelimit
from src.utils.logging import get_logger

router = Router()
logger = get_logger(__name__)

# Hard ceiling on wrong-user admin-command attempts: 3 per 15 min.
_ADMIN_PROBE_LIMIT = 3
_ADMIN_PROBE_WINDOW = 900


def is_admin(user: User) -> bool:
    return user.is_admin or user.id in settings.admin_ids_list


async def _guard(user: User) -> bool:
    """Swallow non-admin calls, counting attempts in Redis for anomaly detection."""
    if is_admin(user):
        return True
    allowed, count = await ratelimit.hit(
        f"admin:probe:{user.id}", _ADMIN_PROBE_LIMIT, _ADMIN_PROBE_WINDOW
    )
    if not allowed:
        logger.warning("admin_probe_threshold", user_id=user.id, count=count)
    return False


@router.message(Command("admin"))
async def cmd_admin(message: Message, user: User, state: FSMContext) -> None:
    if not await _guard(user):
        return
    await message.answer(
        "🛠 <b>Админ-панель</b>\n\n"
        "/admin_balance USER_ID SECONDS — добавить баланс\n"
        "/admin_ban USER_ID — забанить\n"
        "/admin_unban USER_ID — разбанить\n"
        "/admin_stats — статистика",
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
        target_id = int(parts[1])
        seconds = int(parts[2])
    except ValueError:
        await message.answer("Неверные аргументы.")
        return

    target = await get_user(target_id, session)
    if not target:
        await message.answer(f"Пользователь {target_id} не найден.")
        return

    await add_balance(target_id, seconds, session)
    logger.info("admin_add_balance", admin_id=user.id, target_id=target_id, seconds=seconds)
    await message.answer(f"✅ Добавлено {seconds} сек пользователю {target_id}.")


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

    target = await get_user(target_id, session)
    if not target:
        await message.answer(f"Пользователь {target_id} не найден.")
        return

    target.is_banned = True
    await session.commit()
    logger.info("admin_ban", admin_id=user.id, target_id=target_id)
    await message.answer(f"🚫 Пользователь {target_id} заблокирован.")


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
    target = await get_user(target_id, session)
    if not target:
        await message.answer(f"Пользователь {target_id} не найден.")
        return
    target.is_banned = False
    await session.commit()
    logger.info("admin_unban", admin_id=user.id, target_id=target_id)
    await message.answer(f"✅ Пользователь {target_id} разблокирован.")


@router.message(Command("admin_stats"))
async def cmd_admin_stats(
    message: Message, user: User, session: AsyncSession
) -> None:
    if not await _guard(user):
        return

    day_ago = datetime.utcnow() - timedelta(days=1)
    week_ago = datetime.utcnow() - timedelta(days=7)

    total_users = await session.scalar(select(func.count(User.id)))
    banned_users = await session.scalar(
        select(func.count(User.id)).where(User.is_banned.is_(True))
    )
    new_24h = await session.scalar(
        select(func.count(User.id)).where(User.created_at >= day_ago)
    )
    new_7d = await session.scalar(
        select(func.count(User.id)).where(User.created_at >= week_ago)
    )

    done_24h = await session.scalar(
        select(func.count(Transcription.id)).where(
            Transcription.status == "done",
            Transcription.created_at >= day_ago,
        )
    )
    failed_24h = await session.scalar(
        select(func.count(Transcription.id)).where(
            Transcription.status == "failed",
            Transcription.created_at >= day_ago,
        )
    )
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
    )
    pay_sum_24h = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount_rub), 0)).where(
            Transaction.status == "success",
            Transaction.type.in_(["subscription", "topup"]),
            Transaction.created_at >= day_ago,
        )
    ) or 0

    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👤 Пользователей: <b>{total_users or 0}</b> (забанены: {banned_users or 0})\n"
        f"🆕 Новых за 24ч: <b>{new_24h or 0}</b>, за 7д: <b>{new_7d or 0}</b>\n\n"
        f"🎙 Транскрибаций 24ч: <b>{done_24h or 0}</b>, ошибок: <b>{failed_24h or 0}</b>\n"
        f"⏱ Часов озвучки 24ч: <b>{hours_24h}</b>\n\n"
        f"💳 Оплат 24ч: <b>{pay_count_24h or 0}</b> на <b>{float(pay_sum_24h):,.0f}₽</b>\n"
    )
    await message.answer(text, parse_mode="HTML")
