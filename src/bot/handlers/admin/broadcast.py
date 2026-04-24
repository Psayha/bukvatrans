"""Broadcast a message to every non-banned user.

Flow:
  /admin_broadcast  →  bot asks for text
  <admin sends text> →  FSM stores it, asks for confirm (2FA if >1 admin)
  approved          →  background task iterates users and sends

We run send_message sequentially with a tiny delay to stay under
Telegram's 30 msg/s global limit.
"""
import asyncio

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.handlers.admin._common import (
    guard,
    register_approved,
    request_approval,
)
from src.bot.states import AdminFlow
from src.db.models.user import User
from src.services.notification import send_message
from src.utils.logging import get_logger

router = Router()
logger = get_logger(__name__)

_MAX_TEXT_LEN = 3500
_SEND_INTERVAL = 0.05  # 20 msg/s — under the 30/s Telegram soft limit


@router.message(Command("admin_broadcast"))
async def cmd_admin_broadcast(
    message: Message, user: User, state: FSMContext
) -> None:
    if not await guard(user):
        return
    await state.set_state(AdminFlow.broadcast_message)
    await message.answer(
        f"📣 Пришли текст рассылки одним сообщением (до {_MAX_TEXT_LEN} символов). "
        f"Поддерживается HTML. Для отмены: /cancel"
    )


@router.message(AdminFlow.broadcast_message)
async def process_broadcast_text(
    message: Message, user: User, state: FSMContext
) -> None:
    if not await guard(user):
        await state.clear()
        return
    text = (message.text or message.caption or "").strip()
    if not text:
        await message.answer("Пусто. Пришли текст или /cancel.")
        return
    if len(text) > _MAX_TEXT_LEN:
        await message.answer(f"Слишком длинно (> {_MAX_TEXT_LEN}).")
        return

    await state.clear()
    # Stash the text in Redis keyed by the approval token so the executor
    # can fetch it later (handler args have a 64-byte cap).
    import uuid
    broadcast_id = uuid.uuid4().hex[:12]
    await _stash_broadcast(broadcast_id, text)

    await request_approval(
        message, user, "broadcast",
        args=[broadcast_id],
        human=f"broadcast ({len(text)} chars)",
    )


@register_approved("broadcast")
async def _execute_broadcast(
    message: Message, session: AsyncSession, requester_id: int, args: list[str]
) -> None:
    broadcast_id = args[0]
    text = await _fetch_broadcast(broadcast_id)
    if text is None:
        await message.answer("❌ Текст рассылки не найден (истёк TTL).")
        return

    result = await session.execute(
        select(User.id).where(User.is_banned.is_(False))
    )
    recipients = [row[0] for row in result.all()]

    if not recipients:
        await message.answer("Нет получателей.")
        return

    await message.answer(f"📤 Рассылка запущена: {len(recipients)} получателей.")
    asyncio.create_task(_run_broadcast(recipients, text, message))


async def _run_broadcast(recipients: list[int], text: str, status_message: Message) -> None:
    sent, failed = 0, 0
    for uid in recipients:
        try:
            await send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
            logger.debug("broadcast_send_failed", user_id=uid, exc_info=True)
        await asyncio.sleep(_SEND_INTERVAL)

    logger.info("broadcast_done", sent=sent, failed=failed)
    try:
        await status_message.answer(
            f"✅ Рассылка завершена.\nОтправлено: {sent}\nОшибок: {failed}"
        )
    except Exception:
        pass


# Redis stash — broadcast text is too large for a Telegram callback token.

_BROADCAST_TTL = 1800  # 30 min


async def _stash_broadcast(broadcast_id: str, text: str) -> None:
    import redis.asyncio as aioredis
    from src.config import settings
    r = aioredis.from_url(settings.redis_cache_url, decode_responses=True)
    try:
        await r.set(f"admin:broadcast:{broadcast_id}", text, ex=_BROADCAST_TTL)
    finally:
        await r.close()


async def _fetch_broadcast(broadcast_id: str) -> str | None:
    import redis.asyncio as aioredis
    from src.config import settings
    r = aioredis.from_url(settings.redis_cache_url, decode_responses=True)
    try:
        return await r.getdel(f"admin:broadcast:{broadcast_id}")
    finally:
        await r.close()
