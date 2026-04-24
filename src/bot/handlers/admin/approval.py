"""Inline-button callbacks for the two-admin approval flow."""
from aiogram import F, Router
from aiogram.types import CallbackQuery

from src.bot.handlers.admin._common import _execute, is_admin
from src.db.models.user import User
from src.services.notification import send_message
from src.utils import admin_approval

router = Router()


@router.callback_query(F.data.startswith("admin_ok:"))
async def cb_admin_approve(callback: CallbackQuery, user: User) -> None:
    if not is_admin(user):
        await callback.answer("Только для админов.", show_alert=True)
        return
    token = callback.data.split(":", 1)[1]
    req = await admin_approval.consume(token, approver_id=user.id)
    if req is None:
        await callback.answer(
            "Запрос не найден, истёк или нельзя одобрить свой же.",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        f"✅ Одобрено админом <code>{user.id}</code>. Выполняю…",
        parse_mode="HTML",
    )
    await _execute(callback.message, req.requester_id, req.command, req.args)
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
        f"❌ Отклонено админом <code>{user.id}</code>.",
        parse_mode="HTML",
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
