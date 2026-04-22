from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.states import PromoFlow
from src.bot.texts.ru import PROMO_INVALID, PROMO_PROMPT, PROMO_SUCCESS, RATE_LIMIT
from src.db.models.promo_code import PromoCode, PromoCodeUse
from src.db.models.user import User
from src.utils import ratelimit

router = Router()

# Max 5 promo code attempts per user per hour — blunt brute-force.
_PROMO_LIMIT = 5
_PROMO_WINDOW = 3600


@router.message(Command("promo"))
async def cmd_promo(message: Message, state: FSMContext) -> None:
    await message.answer(PROMO_PROMPT)
    await state.set_state(PromoFlow.waiting_code)


@router.message(PromoFlow.waiting_code)
async def process_promo(
    message: Message, user: User, session: AsyncSession, state: FSMContext
) -> None:
    code_str = (message.text or "").strip().upper()
    await state.clear()

    if not code_str or len(code_str) > 50:
        await message.answer(PROMO_INVALID)
        return

    allowed, _ = await ratelimit.hit(
        f"promo:attempts:{user.id}", _PROMO_LIMIT, _PROMO_WINDOW
    )
    if not allowed:
        await message.answer(RATE_LIMIT)
        return

    reward_text = await _apply_promo(user, code_str, session)
    if reward_text is None:
        await message.answer(PROMO_INVALID)
    else:
        # On success, reset the counter so genuine usage isn't penalised.
        await ratelimit.reset(f"promo:attempts:{user.id}")
        await message.answer(PROMO_SUCCESS.format(reward=reward_text))


async def _apply_promo(user: User, code_str: str, session: AsyncSession) -> str | None:
    """Apply promo code atomically. Returns reward text on success, None otherwise."""
    try:
        async with session.begin():
            # Row-lock the promo so concurrent users can't exceed max_uses.
            stmt = (
                select(PromoCode)
                .where(PromoCode.code == code_str, PromoCode.is_active.is_(True))
                .with_for_update()
            )
            try:
                result = await session.execute(stmt)
            except Exception:
                result = await session.execute(
                    select(PromoCode).where(
                        PromoCode.code == code_str, PromoCode.is_active.is_(True)
                    )
                )
            promo = result.scalar_one_or_none()
            if not promo:
                return None

            if promo.expires_at and promo.expires_at < datetime.utcnow():
                return None
            if promo.max_uses and promo.used_count >= promo.max_uses:
                return None

            # Unique constraint (promo_code_id, user_id) gives us idempotency —
            # a duplicate apply will raise IntegrityError.
            use_result = await session.execute(
                select(PromoCodeUse).where(
                    PromoCodeUse.promo_code_id == promo.id,
                    PromoCodeUse.user_id == user.id,
                )
            )
            if use_result.scalar_one_or_none():
                return None

            reward_text = ""
            if promo.type == "free_seconds":
                # Increment in place while row is locked.
                user_row = await session.get(User, user.id, with_for_update=True)
                if user_row is None:
                    user_row = user
                user_row.balance_seconds = (user_row.balance_seconds or 0) + promo.value
                hours = promo.value // 3600
                minutes = (promo.value % 3600) // 60
                reward_text = (
                    f"{hours} ч {minutes} мин" if hours else f"{minutes} мин"
                )

            session.add(PromoCodeUse(promo_code_id=promo.id, user_id=user.id))
            promo.used_count += 1
            return reward_text
    except Exception:
        return None
