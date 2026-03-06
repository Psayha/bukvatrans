from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.billing import calculate_referral_bonus_rub, rub_to_seconds
from src.db.repositories.user import add_balance, get_user
from src.db.models.referral import Referral
from src.db.models.transaction import Transaction
import uuid


def calculate_bonus_seconds(payment_amount_rub: float) -> float:
    """Return referral bonus in rubles (20% of payment)."""
    return calculate_referral_bonus_rub(payment_amount_rub)


async def process_referral_bonus(
    referrer_id: Optional[int],
    payment_amount_rub: float,
    session: AsyncSession,
) -> None:
    """Credit referral bonus to referrer if applicable."""
    if referrer_id is None:
        return

    referrer = await get_user(referrer_id, session)
    if not referrer:
        return

    bonus_rub = calculate_referral_bonus_rub(payment_amount_rub)
    bonus_seconds = rub_to_seconds(bonus_rub)

    await add_balance(referrer_id, bonus_seconds, session)

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
    await session.commit()
