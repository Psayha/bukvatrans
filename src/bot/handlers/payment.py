import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.handlers.test_payment import build_test_payment_button
from src.bot.keyboards.inline import payment_link_kb, subscribe_kb, topup_kb
from src.bot.states import PaymentFlow
from src.bot.texts.ru import (
    EMAIL_INVALID,
    EMAIL_REQUEST,
    EMAIL_SAVED,
    PAYMENT_CREATED,
    SUBSCRIBE_TEXT,
)
from src.db.models.user import User
from src.services.billing import PLANS, TOPUP_OPTIONS

router = Router()

# Permissive email check — ЮKassa and the ОФД will do strict validation.
# This just catches obvious typos before creating a payment.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _plan_label(plan_key: str) -> str:
    return PLANS[plan_key].get("label", plan_key)


TOPUP_NAMES = {
    "topup_99": "2 часа",
    "topup_299": "7 часов",
    "topup_499": "12 часов",
}


@router.message(Command("subscribe", "subscription", "plans"))
async def cmd_subscribe(message: Message) -> None:
    kb = subscribe_kb()
    # In non-prod envs, prepend a test-payment shortcut. In prod this is a
    # no-op (returns None) so the menu looks exactly like the live version.
    test_btn = build_test_payment_button()
    if test_btn is not None:
        kb.inline_keyboard.insert(0, [test_btn])
    await message.answer(SUBSCRIBE_TEXT, reply_markup=kb, parse_mode="HTML")


@router.message(Command("topup"))
async def cmd_topup(message: Message) -> None:
    kb = topup_kb()
    test_btn = build_test_payment_button()
    if test_btn is not None:
        kb.inline_keyboard.insert(0, [test_btn])
    await message.answer("Выберите сумму пополнения:", reply_markup=kb)


async def _start_or_request_email(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    state: FSMContext,
    *,
    plan_key: str | None = None,
    topup_key: str | None = None,
) -> None:
    """Branch: if we already know the user's email, create the payment; else
    stash the chosen plan in FSM and ask for an email."""
    if user.email:
        await _create_and_send_payment(
            callback.message, user, session,
            plan_key=plan_key, topup_key=topup_key,
        )
        await callback.answer()
        return

    # Ask for email, then the next message handler creates the payment.
    await state.set_state(PaymentFlow.awaiting_email)
    await state.update_data(plan_key=plan_key, topup_key=topup_key)
    await callback.message.answer(EMAIL_REQUEST)
    await callback.answer()


@router.callback_query(F.data.startswith("plan:"))
async def cb_plan(
    callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext
) -> None:
    plan_key = callback.data.split(":", 1)[1]
    if plan_key not in PLANS:
        await callback.answer("Неизвестный тариф.", show_alert=True)
        return
    await _start_or_request_email(callback, user, session, state, plan_key=plan_key)


@router.callback_query(F.data.startswith("topup:"))
async def cb_topup(
    callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext
) -> None:
    topup_key = callback.data.split(":", 1)[1]

    if topup_key == "menu":
        await callback.message.edit_text("Выберите сумму пополнения:", reply_markup=topup_kb())
        await callback.answer()
        return

    if topup_key == "back":
        await callback.message.edit_text(SUBSCRIBE_TEXT, reply_markup=subscribe_kb(), parse_mode="HTML")
        await callback.answer()
        return

    if topup_key not in TOPUP_OPTIONS:
        await callback.answer("Неизвестный тариф.", show_alert=True)
        return

    await _start_or_request_email(callback, user, session, state, topup_key=topup_key)


@router.message(PaymentFlow.awaiting_email)
async def on_email(
    message: Message, user: User, session: AsyncSession, state: FSMContext
) -> None:
    email = (message.text or "").strip().lower()
    if not _EMAIL_RE.match(email) or len(email) > 255:
        await message.answer(EMAIL_INVALID)
        return

    user.email = email
    await session.commit()

    data = await state.get_data()
    plan_key = data.get("plan_key")
    topup_key = data.get("topup_key")
    await state.clear()

    await message.answer(EMAIL_SAVED)
    await _create_and_send_payment(
        message, user, session, plan_key=plan_key, topup_key=topup_key
    )


async def _create_and_send_payment(
    message: Message,
    user: User,
    session: AsyncSession,
    *,
    plan_key: str | None,
    topup_key: str | None,
) -> None:
    if plan_key:
        plan = PLANS[plan_key]
        plan_name = _plan_label(plan_key)
        amount = plan["price_rub"]
        metadata = {"plan_key": plan_key, "user_id": str(user.id)}
    elif topup_key:
        option = TOPUP_OPTIONS[topup_key]
        plan_name = f"Пополнение {TOPUP_NAMES.get(topup_key, topup_key)}"
        amount = option["price_rub"]
        metadata = {"topup_key": topup_key, "user_id": str(user.id)}
    else:
        return

    payment_url = await _create_yukassa_payment(
        user_id=user.id,
        amount_rub=amount,
        description=plan_name,
        metadata=metadata,
        customer_email=user.email or "",
        session=session,
    )

    await message.answer(
        PAYMENT_CREATED.format(plan_name=plan_name, amount=amount),
        reply_markup=payment_link_kb(payment_url),
        parse_mode="HTML",
    )


async def _create_yukassa_payment(
    user_id: int,
    amount_rub: float,
    description: str,
    metadata: dict,
    customer_email: str,
    session: AsyncSession,
) -> str:
    """Create a YuKassa payment with 54-ФЗ fiscal receipt; return pay URL."""
    import asyncio
    import uuid as _uuid

    from yookassa import Configuration, Payment

    from src.config import settings

    Configuration.account_id = settings.YUKASSA_SHOP_ID
    Configuration.secret_key = settings.YUKASSA_SECRET_KEY

    # 54-ФЗ requires a fiscal receipt for every B2C payment. YuKassa
    # forwards the receipt to the ОФД when `receipt` is attached to the
    # payment. `vat_code` is set via YUKASSA_VAT_CODE (1 = без НДС / УСН).
    receipt: dict = {
        "items": [
            {
                "description": description[:128],
                "quantity": "1.00",
                "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                "vat_code": settings.YUKASSA_VAT_CODE,
                "payment_subject": "service",
                "payment_mode": "full_payment",
            }
        ],
    }
    if customer_email:
        receipt["customer"] = {"email": customer_email}

    def _create():
        payment = Payment.create(
            {
                "amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
                "confirmation": {
                    "type": "redirect",
                    "return_url": f"https://t.me/{settings.BOT_TOKEN.split(':')[0]}",
                },
                "capture": True,
                "description": description,
                "metadata": metadata,
                "receipt": receipt,
            },
            str(_uuid.uuid4()),
        )
        return payment.confirmation.confirmation_url

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _create)
