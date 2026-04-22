"""Integration tests for complete billing flow."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import select

from src.db.models.user import User
from src.db.models.subscription import Subscription
from src.db.models.transaction import Transaction
from src.db.repositories.user import add_balance, deduct_balance, get_user
from src.db.repositories.transaction import create_transaction
from src.services.billing import calculate_charge, check_can_transcribe, PLANS


class TestFullBillingFlow:
    @pytest.mark.asyncio
    async def test_new_user_has_3_free_uses(self, db_session):
        from src.db.repositories.user import get_or_create_user
        user, created = await get_or_create_user(
            user_id=600001,
            username="newbie",
            first_name="New",
            last_name=None,
            referrer_id=None,
            session=db_session,
        )
        assert created is True
        assert user.free_uses_left == 3
        assert user.balance_seconds == 0

    @pytest.mark.asyncio
    async def test_free_user_can_transcribe_without_balance(self, db_session):
        from src.db.repositories.user import get_or_create_user
        user, _ = await get_or_create_user(
            user_id=600002,
            username="freebie",
            first_name="Free",
            last_name=None,
            referrer_id=None,
            session=db_session,
        )
        can, reason = await check_can_transcribe(user, estimated_duration=1800)
        assert can is True

    @pytest.mark.asyncio
    async def test_balance_deduction_after_transcription(self, db_session, test_user):
        initial = test_user.balance_seconds
        duration = 4500  # 75 min
        charge = calculate_charge(duration)  # 4500 → 4500 (exact 75 min)

        user = await deduct_balance(test_user.id, charge, db_session)
        assert user.balance_seconds == initial - charge

    @pytest.mark.asyncio
    async def test_refund_restores_balance(self, db_session, test_user):
        initial = test_user.balance_seconds
        charge = 3600

        # Deduct then refund
        await deduct_balance(test_user.id, charge, db_session)
        user = await add_balance(test_user.id, charge, db_session)
        assert user.balance_seconds == initial

    @pytest.mark.asyncio
    async def test_unlimited_sub_no_deduction_needed(self, db_session, user_with_unlimited_sub):
        can, _ = await check_can_transcribe(user_with_unlimited_sub, estimated_duration=99999)
        assert can is True
        # Balance stays at 0 — unlimited sub means no deduction
        assert user_with_unlimited_sub.balance_seconds == 0

    @pytest.mark.asyncio
    async def test_transaction_recorded_on_topup(self, db_session, test_user):
        await create_transaction(
            user_id=test_user.id,
            type_="topup",
            status="success",
            amount_rub=99.0,
            seconds_added=7200,
            yukassa_id="yk_test_topup",
            session=db_session,
        )
        await add_balance(test_user.id, 7200, db_session)

        await get_user(test_user.id, db_session)
        result = await db_session.execute(
            select(Transaction).where(Transaction.yukassa_id == "yk_test_topup")
        )
        tx = result.scalar_one_or_none()
        assert tx is not None
        assert tx.seconds_added == 7200

    @pytest.mark.asyncio
    async def test_charge_rounding_is_per_minute(self, db_session, test_user):
        """1 second over a minute → charged full minute."""
        duration_61s = 61
        charge = calculate_charge(duration_61s)
        assert charge == 120  # 2 full minutes

        duration_59s = 59
        charge = calculate_charge(duration_59s)
        assert charge == 60  # 1 full minute

    @pytest.mark.asyncio
    async def test_subscription_activation_adds_seconds(self, db_session):
        user = User(id=700001, balance_seconds=0, free_uses_left=0)
        db_session.add(user)
        await db_session.commit()

        plan = PLANS["basic_monthly"]
        await add_balance(user.id, plan["seconds"], db_session)

        sub = Subscription(
            user_id=user.id,
            plan="basic",
            status="active",
            seconds_limit=plan["seconds"],
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        db_session.add(sub)
        await db_session.commit()

        updated = await get_user(user.id, db_session)
        assert updated.balance_seconds == plan["seconds"]
