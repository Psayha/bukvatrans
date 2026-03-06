from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User
from src.services.billing import PLANS, TOPUP_OPTIONS
from src.bot.texts.ru import SUBSCRIBE_TEXT, PAYMENT_CREATED
from src.bot.keyboards.inline import subscribe_kb, topup_kb, payment_link_kb

router = Router()

PLAN_NAMES = {
    "basic_monthly": "Базовый — 1 месяц",
    "basic_yearly": "Базовый — 1 год",
    "pro_monthly": "Про — 1 месяц",
    "pro_yearly": "Про — 1 год",
}

TOPUP_NAMES = {
    "topup_99": "2 часа",
    "topup_299": "7 часов",
    "topup_499": "12 часов",
}


@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message) -> None:
    await message.answer(SUBSCRIBE_TEXT, reply_markup=subscribe_kb(), parse_mode="HTML")


@router.message(Command("topup"))
async def cmd_topup(message: Message) -> None:
    await message.answer("Выберите сумму пополнения:", reply_markup=topup_kb())


@router.callback_query(F.data.startswith("plan:"))
async def cb_plan(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    plan_key = callback.data.split(":", 1)[1]
    if plan_key not in PLANS:
        await callback.answer("Неизвестный тариф.", show_alert=True)
        return

    plan = PLANS[plan_key]
    plan_name = PLAN_NAMES.get(plan_key, plan_key)

    payment_url = await _create_yukassa_payment(
        user_id=user.id,
        amount_rub=plan["price_rub"],
        description=plan_name,
        metadata={"plan_key": plan_key, "user_id": str(user.id)},
        session=session,
    )

    await callback.message.answer(
        PAYMENT_CREATED.format(plan_name=plan_name, amount=plan["price_rub"]),
        reply_markup=payment_link_kb(payment_url),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("topup:"))
async def cb_topup(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
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

    option = TOPUP_OPTIONS[topup_key]
    option_name = f"Пополнение {TOPUP_NAMES.get(topup_key, topup_key)}"

    payment_url = await _create_yukassa_payment(
        user_id=user.id,
        amount_rub=option["price_rub"],
        description=option_name,
        metadata={"topup_key": topup_key, "user_id": str(user.id)},
        session=session,
    )

    await callback.message.answer(
        PAYMENT_CREATED.format(plan_name=option_name, amount=option["price_rub"]),
        reply_markup=payment_link_kb(payment_url),
        parse_mode="HTML",
    )
    await callback.answer()


async def _create_yukassa_payment(
    user_id: int,
    amount_rub: float,
    description: str,
    metadata: dict,
    session: AsyncSession,
) -> str:
    """Create a YuKassa payment and return the payment URL."""
    from yookassa import Configuration, Payment
    import uuid as _uuid
    from src.config import settings

    Configuration.account_id = settings.YUKASSA_SHOP_ID
    Configuration.secret_key = settings.YUKASSA_SECRET_KEY

    import asyncio

    def _create():
        payment = Payment.create({
            "amount": {"value": str(amount_rub), "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": f"https://t.me/{settings.BOT_TOKEN.split(':')[0]}",
            },
            "capture": True,
            "description": description,
            "metadata": metadata,
        }, str(_uuid.uuid4()))
        return payment.confirmation.confirmation_url

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _create)
