import pytest

from src.db.models.user import User
from src.services.referral import calculate_bonus_seconds, process_referral_bonus
from src.services.billing import RUB_TO_SECONDS


class TestCalculateBonusSeconds:
    def test_20_percent_of_649(self):
        """20% of 649₽ = 129.8₽."""
        bonus_rub = calculate_bonus_seconds(649.0)
        assert abs(bonus_rub - 129.8) < 0.01

    def test_zero_payment(self):
        assert calculate_bonus_seconds(0.0) == 0.0

    def test_100_rub(self):
        bonus = calculate_bonus_seconds(100.0)
        assert abs(bonus - 20.0) < 0.01


class TestProcessReferralBonus:
    @pytest.mark.asyncio
    async def test_no_bonus_without_referrer(self, test_user, db_session):
        test_user.referrer_id = None
        initial_balance = test_user.balance_seconds

        await process_referral_bonus(
            referrer_id=None,
            payment_amount_rub=649.0,
            session=db_session,
        )
        await db_session.refresh(test_user)
        assert test_user.balance_seconds == initial_balance

    @pytest.mark.asyncio
    async def test_referrer_receives_bonus(self, db_session):
        referrer = User(id=777001, balance_seconds=0, free_uses_left=0)
        referred = User(id=777002, balance_seconds=0, free_uses_left=0, referrer_id=777001)
        db_session.add_all([referrer, referred])
        await db_session.commit()

        await process_referral_bonus(
            referrer_id=referrer.id,
            payment_amount_rub=649.0,
            session=db_session,
        )
        await db_session.refresh(referrer)

        expected_bonus_rub = 649.0 * 0.20
        expected_seconds = int(expected_bonus_rub * RUB_TO_SECONDS)
        assert referrer.balance_seconds == expected_seconds

    @pytest.mark.asyncio
    async def test_nonexistent_referrer_no_error(self, db_session):
        """Should not raise even if referrer doesn't exist."""
        await process_referral_bonus(
            referrer_id=999999,
            payment_amount_rub=649.0,
            session=db_session,
        )

    @pytest.mark.asyncio
    async def test_transaction_created_for_referrer(self, db_session):
        from sqlalchemy import select
        from src.db.models.transaction import Transaction

        referrer = User(id=888001, balance_seconds=0, free_uses_left=0)
        db_session.add(referrer)
        await db_session.commit()

        await process_referral_bonus(
            referrer_id=referrer.id,
            payment_amount_rub=1000.0,
            session=db_session,
        )

        result = await db_session.execute(
            select(Transaction).where(
                Transaction.user_id == referrer.id,
                Transaction.type == "referral_bonus",
            )
        )
        transaction = result.scalar_one_or_none()
        assert transaction is not None
        assert transaction.status == "success"
        assert abs(float(transaction.amount_rub) - 200.0) < 0.01
