"""Dev-only: let users exercise the post-payment flow without ЮKassa.

When ENV != "production", /subscribe and /topup get an extra
"🧪 Тест без оплаты" button that opens a submenu of every plan and
topup. Picking one calls the real `_handle_payment_succeeded` with a
synthesised payment — so subscription creation, balance credit,
transaction row and referral bonus all run exactly as on live payment.

Visibility is checked both at menu build time and again inside each
callback, so flipping ENV → production disables the flow even if a
stale button is cached in someone's chat.
"""
import uuid

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from src.bot.keyboards.inline import subscribe_kb
from src.bot.texts.ru import SUBSCRIBE_TEXT
from src.config import settings
from src.db.models.user import User
from src.services.billing import PLANS, TOPUP_OPTIONS
from src.utils.logging import get_logger

router = Router()
logger = get_logger(__name__)


_PLAN_LABELS = {
    "basic_monthly": "Базовый — 1 мес",
    "basic_yearly": "Базовый — 1 год",
    "pro_monthly": "Про — 1 мес",
    "pro_yearly": "Про — 1 год",
}
_TOPUP_LABELS = {
    "topup_99": "2 часа",
    "topup_299": "7 часов",
    "topup_499": "12 часов",
}


def _is_enabled() -> bool:
    return settings.ENV != "production"


def build_test_payment_button() -> InlineKeyboardButton | None:
    """Returned by the subscribe-command handler to prepend to the keyboard."""
    if not _is_enabled():
        return None
    return InlineKeyboardButton(
        text="🧪 Тест без оплаты",
        callback_data="testpay:menu",
    )


def _testpay_kb() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for key, plan in PLANS.items():
        rows.append([
            InlineKeyboardButton(
                text=f"🧪 {_PLAN_LABELS.get(key, key)} ({plan['price_rub']:.0f}₽)",
                callback_data=f"testpay:plan:{key}",
            )
        ])
    for key, topup in TOPUP_OPTIONS.items():
        rows.append([
            InlineKeyboardButton(
                text=f"🧪 Пополнение {_TOPUP_LABELS.get(key, key)} ({topup['price_rub']:.0f}₽)",
                callback_data=f"testpay:topup:{key}",
            )
        ])
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="testpay:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "testpay:menu")
async def cb_testpay_menu(callback: CallbackQuery) -> None:
    if not _is_enabled():
        await callback.answer("Недоступно в production.", show_alert=True)
        return
    await callback.message.edit_text(
        "🧪 <b>Тестовая оплата</b>\n\n"
        "Выбери тариф — он активируется сразу, без реальных денег.\n"
        "Этот путь доступен только пока ENV ≠ production.",
        reply_markup=_testpay_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "testpay:back")
async def cb_testpay_back(callback: CallbackQuery) -> None:
    # Re-enter the regular subscribe menu.
    kb = subscribe_kb()
    if _is_enabled():
        kb.inline_keyboard.insert(0, [build_test_payment_button()])
    await callback.message.edit_text(
        SUBSCRIBE_TEXT, reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("testpay:plan:"))
async def cb_testpay_plan(callback: CallbackQuery, user: User) -> None:
    if not _is_enabled():
        await callback.answer("Недоступно в production.", show_alert=True)
        return
    plan_key = callback.data.split(":", 2)[2]
    if plan_key not in PLANS:
        await callback.answer("Неизвестный тариф.", show_alert=True)
        return
    await _simulate_and_report(callback, user, plan_key=plan_key)


@router.callback_query(F.data.startswith("testpay:topup:"))
async def cb_testpay_topup(callback: CallbackQuery, user: User) -> None:
    if not _is_enabled():
        await callback.answer("Недоступно в production.", show_alert=True)
        return
    topup_key = callback.data.split(":", 2)[2]
    if topup_key not in TOPUP_OPTIONS:
        await callback.answer("Неизвестный тариф.", show_alert=True)
        return
    await _simulate_and_report(callback, user, topup_key=topup_key)


async def _simulate_and_report(
    callback: CallbackQuery,
    user: User,
    *,
    plan_key: str | None = None,
    topup_key: str | None = None,
) -> None:
    from src.api.webhooks import _handle_payment_succeeded
    from src.db.base import async_session_factory

    if plan_key:
        price = PLANS[plan_key]["price_rub"]
        metadata = {"user_id": str(user.id), "plan_key": plan_key}
        label = _PLAN_LABELS.get(plan_key, plan_key)
    else:
        price = TOPUP_OPTIONS[topup_key]["price_rub"]
        metadata = {"user_id": str(user.id), "topup_key": topup_key}
        label = _TOPUP_LABELS.get(topup_key, topup_key)

    fake_payment = {
        "id": f"testpay_{uuid.uuid4().hex[:24]}",
        "status": "succeeded",
        "amount": {"value": f"{price:.2f}", "currency": "RUB"},
        "metadata": metadata,
        "paid": True,
    }

    try:
        async with async_session_factory() as session:
            await _handle_payment_succeeded(
                fake_payment,
                idempotency_key=f"testpay-{uuid.uuid4().hex[:8]}",
                session=session,
            )
    except Exception as e:
        logger.error("user_testpay_failed", user_id=user.id, exc_info=True)
        await callback.answer(f"Ошибка: {type(e).__name__}", show_alert=True)
        return

    logger.info(
        "user_testpay_executed",
        user_id=user.id,
        plan=plan_key,
        topup=topup_key,
        amount_rub=price,
    )
    await callback.message.edit_text(
        f"✅ <b>Тестовая оплата симулирована</b>\n\n"
        f"Тариф: <b>{label}</b>\n"
        f"Сумма: {price:.0f}₽ (не списано)\n\n"
        f"Подписка/баланс уже начислены — проверь /balance.",
        parse_mode="HTML",
    )
    await callback.answer("Готово ✓")
