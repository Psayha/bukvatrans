import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.transaction import Transaction
from src.db.models.user import User
from src.services.billing import calculate_referral_bonus_rub, rub_to_seconds


def calculate_bonus_seconds(payment_amount_rub: float) -> float:
    """Return referral bonus in rubles (20% of payment)."""
    return calculate_referral_bonus_rub(payment_amount_rub)


async def _lock_referrer(user_id: int, session: AsyncSession) -> Optional[User]:
    stmt = select(User).where(User.id == user_id).with_for_update()
    try:
        result = await session.execute(stmt)
    except Exception:
        result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def process_referral_bonus(
    referrer_id: Optional[int],
    payment_amount_rub: float,
    session: AsyncSession,
    autocommit: bool = True,
) -> None:
    """Credit referral bonus to referrer.

    When called from within an outer `session.begin()` block, pass
    `autocommit=False` so the caller controls commit boundaries.
    """
    if referrer_id is None:
        return

    referrer = await _lock_referrer(referrer_id, session)
    if not referrer:
        return

    bonus_rub = calculate_referral_bonus_rub(payment_amount_rub)
    bonus_seconds = rub_to_seconds(bonus_rub)

    referrer.balance_seconds = (referrer.balance_seconds or 0) + bonus_seconds

    transaction = Transaction(
        id=str(uuid.uuid4()),
        user_id=referrer_id,
        type="referral_bonus",
        status="success",
        amount_rub=bonus_rub,
        seconds_added=bonus_seconds,
        description=f"Реферальный бонус 20% от {payment_amount_rub}₽",
    )
    session.add(transaction)

    if autocommit:
        await session.commit()
