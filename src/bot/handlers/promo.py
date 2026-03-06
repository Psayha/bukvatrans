from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User
from src.db.models.promo_code import PromoCode, PromoCodeUse
from src.db.repositories.user import add_balance
from src.bot.states import PromoFlow
from src.bot.texts.ru import PROMO_PROMPT, PROMO_SUCCESS, PROMO_INVALID

router = Router()


@router.message(Command("promo"))
async def cmd_promo(message: Message, state: FSMContext) -> None:
    await message.answer(PROMO_PROMPT)
    await state.set_state(PromoFlow.waiting_code)


@router.message(PromoFlow.waiting_code)
async def process_promo(message: Message, user: User, session: AsyncSession, state: FSMContext) -> None:
    code_str = message.text.strip().upper()
    await state.clear()

    # Find promo code
    result = await session.execute(
        select(PromoCode).where(PromoCode.code == code_str, PromoCode.is_active.is_(True))
    )
    promo = result.scalar_one_or_none()

    if not promo:
        await message.answer(PROMO_INVALID)
        return

    # Check expiry
    if promo.expires_at and promo.expires_at < datetime.utcnow():
        await message.answer(PROMO_INVALID)
        return

    # Check max uses
    if promo.max_uses and promo.used_count >= promo.max_uses:
        await message.answer(PROMO_INVALID)
        return

    # Check user already used it
    use_result = await session.execute(
        select(PromoCodeUse).where(
            PromoCodeUse.promo_code_id == promo.id,
            PromoCodeUse.user_id == user.id,
        )
    )
    if use_result.scalar_one_or_none():
        await message.answer(PROMO_INVALID)
        return

    # Apply promo
    reward_text = ""
    if promo.type == "free_seconds":
        await add_balance(user.id, promo.value, session)
        hours = promo.value // 3600
        minutes = (promo.value % 3600) // 60
        reward_text = f"{hours} ч {minutes} мин" if hours else f"{minutes} мин"

    # Record usage
    use = PromoCodeUse(promo_code_id=promo.id, user_id=user.id)
    session.add(use)
    promo.used_count += 1
    await session.commit()

    await message.answer(PROMO_SUCCESS.format(reward=reward_text))
