"""Shared admin helpers: auth guard and two-admin approval plumbing.

Submodules register their approved executors via `@register_approved("name")`.
When a second admin clicks Approve, we look up the name in `APPROVED_HANDLERS`
and call the executor with a fresh DB session. This lets each command live in
its own small file without a giant switch in _execute.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models.user import User
from src.services.notification import send_message
from src.utils import admin_approval, ratelimit
from src.utils.logging import get_logger

logger = get_logger(__name__)

_ADMIN_PROBE_LIMIT = 3
_ADMIN_PROBE_WINDOW = 900


def is_admin(user: User) -> bool:
    return user.is_admin or user.id in settings.admin_ids_list


async def guard(user: User) -> bool:
    """Accept admins, silently drop and log repeat non-admin probes."""
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


ExecutorFn = Callable[[Message, AsyncSession, int, list[str]], Awaitable[None]]
APPROVED_HANDLERS: dict[str, ExecutorFn] = {}


def register_approved(name: str) -> Callable[[ExecutorFn], ExecutorFn]:
    """Decorator: submodules register how their approved action should run."""
    def decorator(fn: ExecutorFn) -> ExecutorFn:
        APPROVED_HANDLERS[name] = fn
        return fn
    return decorator


async def request_approval(
    message: Message,
    requester: User,
    command: str,
    args: list[str],
    human: str,
) -> None:
    """Either execute inline (solo-admin deployment) or DM other admins for
    approval. Solo-admin bypass is deliberate: a one-admin bot shouldn't be
    locked out of its own controls."""
    other_ids = _other_admin_ids(requester.id)
    if not other_ids:
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
                aid,
                text,
                parse_mode="HTML",
                reply_markup=_approval_kb(token).model_dump(by_alias=True),
            )
        except Exception:
            logger.warning("admin_approval_dm_failed", admin_id=aid, exc_info=True)
    await message.answer(
        f"🕐 Ожидаю подтверждение от второго админа "
        f"(≤ {settings.ADMIN_APPROVAL_TTL_SECONDS // 60} мин).",
    )


async def _execute(
    message: Message, requester_id: int, command: str, args: list[str]
) -> None:
    """Dispatch an approved action to its registered handler. A fresh session
    is always opened because the original handler's session may have been
    closed by the time the second admin approves."""
    from src.db.base import async_session_factory

    handler = APPROVED_HANDLERS.get(command)
    if handler is None:
        await message.answer(f"⚠️ Неизвестная команда: {command}")
        logger.error("admin_unknown_approved_command", command=command)
        return

    async with async_session_factory() as session:
        try:
            await handler(message, session, requester_id, args)
        except Exception as e:
            logger.error("admin_execute_failed", command=command, exc_info=True)
            await message.answer(f"❌ Ошибка при выполнении: {type(e).__name__}: {e}")


# Re-exported for the public API of this package.
__all__ = [
    "APPROVED_HANDLERS",
    "guard",
    "is_admin",
    "register_approved",
    "request_approval",
    "_execute",
]
