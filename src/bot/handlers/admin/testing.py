"""Dev-only helpers. Refuses to run when ENV=production.

Right now: `/admin_testpay` simulates a successful YuKassa webhook so you
can exercise the post-payment flow (subscription, balance credit, referral
bonus) without touching real money."""
import uuid

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.handlers.admin._common import guard
from src.config import settings
from src.db.models.user import User
from src.services.billing import PLANS, TOPUP_OPTIONS
from src.utils.logging import get_logger

router = Router()
logger = get_logger(__name__)


@router.message(Command("admin_testpay"))
async def cmd_admin_testpay(
    message: Message, user: User, session: AsyncSession
) -> None:
    if not await guard(user):
        return

    if settings.ENV == "production":
        await message.answer("❌ /admin_testpay заблокирован в production.")
        return

    parts = (message.text or "").split()
    if len(parts) not in (2, 3):
        await message.answer(
            "Использование: <code>/admin_testpay PLAN_KEY [USER_ID]</code>\n\n"
            f"Подписки: {', '.join(PLANS)}\n"
            f"Пополнения: {', '.join(TOPUP_OPTIONS)}",
            parse_mode="HTML",
        )
        return

    plan_key = parts[1]
    try:
        target_id = int(parts[2]) if len(parts) == 3 else user.id
    except ValueError:
        await message.answer("Неверный USER_ID.")
        return

    is_plan = plan_key in PLANS
    is_topup = plan_key in TOPUP_OPTIONS
    if not is_plan and not is_topup:
        await message.answer("Неизвестный тариф.")
        return

    price = (PLANS if is_plan else TOPUP_OPTIONS)[plan_key]["price_rub"]
    metadata = {"user_id": str(target_id)}
    metadata["plan_key" if is_plan else "topup_key"] = plan_key

    fake_payment = {
        "id": f"test_{uuid.uuid4().hex[:24]}",
        "status": "succeeded",
        "amount": {"value": f"{price:.2f}", "currency": "RUB"},
        "metadata": metadata,
        "paid": True,
    }

    # Re-use the real webhook handler. It opens its own session.begin(),
    # so any failure rolls back cleanly.
    from src.api.webhooks import _handle_payment_succeeded
    from src.db.base import async_session_factory

    try:
        async with async_session_factory() as fresh_session:
            await _handle_payment_succeeded(
                fake_payment,
                idempotency_key=f"testpay-{uuid.uuid4().hex[:8]}",
                session=fresh_session,
            )
    except Exception as e:
        logger.error("admin_testpay_failed", admin_id=user.id, exc_info=True)
        await message.answer(f"❌ Ошибка симуляции: {type(e).__name__}: {e}")
        return

    logger.warning(
        "admin_testpay_executed",
        admin_id=user.id,
        target_id=target_id,
        plan=plan_key,
        amount_rub=price,
    )
    await message.answer(
        f"✅ Симулирована оплата <code>{plan_key}</code> "
        f"({price}₽) пользователю {target_id}.",
        parse_mode="HTML",
    )
