import pytest
from src.services.billing import (
    calculate_charge,
    check_can_transcribe,
    rub_to_seconds,
    calculate_referral_bonus_rub,
    RUB_TO_SECONDS,
    REFERRAL_BONUS_PERCENT,
)
from src.db.models.user import User


class TestCalculateCharge:
    def test_exact_minute(self):
        """Exactly 60 seconds → 60 seconds charged."""
        assert calculate_charge(60) == 60

    def test_rounds_up(self):
        """61 seconds → rounds up to 120."""
        assert calculate_charge(61) == 120

    def test_one_second(self):
        """1 second → rounds up to 60."""
        assert calculate_charge(1) == 60

    def test_zero_duration(self):
        """0 seconds → 0."""
        assert calculate_charge(0) == 0

    def test_negative_duration(self):
        """Negative → 0."""
        assert calculate_charge(-10) == 0

    def test_large_file_rounds_up(self):
        """1h 30m 1s → rounds up to 91 min = 5460s."""
        assert calculate_charge(5401) == 5460

    def test_exactly_one_hour(self):
        """3600 seconds → 3600 (no rounding needed)."""
        assert calculate_charge(3600) == 3600

    def test_59_seconds(self):
        """59s → 60s."""
        assert calculate_charge(59) == 60

    def test_120_seconds(self):
        """120s → 120s (exact minute)."""
        assert calculate_charge(120) == 120

    def test_121_seconds(self):
        """121s → 180s."""
        assert calculate_charge(121) == 180


class TestCheckCanTranscribe:
    @pytest.mark.asyncio
    async def test_banned_user_cannot_transcribe(self, banned_user):
        can, msg = await check_can_transcribe(banned_user)
        assert can is False
        assert "заблокирован" in msg

    @pytest.mark.asyncio
    async def test_free_uses_allow_transcribe(self, user_with_free_uses):
        can, msg = await check_can_transcribe(user_with_free_uses, estimated_duration=3600)
        assert can is True
        assert msg == ""

    @pytest.mark.asyncio
    async def test_unlimited_subscription_allows_transcribe(self, user_with_unlimited_sub):
        can, msg = await check_can_transcribe(user_with_unlimited_sub, estimated_duration=99999)
        assert can is True
        assert msg == ""

    @pytest.mark.asyncio
    async def test_zero_balance_blocked(self, db_session):
        user = User(id=9001, balance_seconds=0, free_uses_left=0)
        can, msg = await check_can_transcribe(user)
        assert can is False
        assert "баланса" in msg

    @pytest.mark.asyncio
    async def test_sufficient_balance(self, test_user):
        can, msg = await check_can_transcribe(test_user, estimated_duration=3600)
        assert can is True

    @pytest.mark.asyncio
    async def test_insufficient_balance_for_file(self, test_user):
        test_user.balance_seconds = 60
        can, msg = await check_can_transcribe(test_user, estimated_duration=3600)
        assert can is False
        assert "баланса" in msg

    @pytest.mark.asyncio
    async def test_url_no_duration_estimate(self, test_user):
        """For URL sources, no duration estimate — only check balance > 0."""
        test_user.balance_seconds = 1
        can, msg = await check_can_transcribe(test_user, estimated_duration=None)
        assert can is True


class TestRubToSeconds:
    def test_one_rub(self):
        assert rub_to_seconds(1.0) == RUB_TO_SECONDS

    def test_zero(self):
        assert rub_to_seconds(0.0) == 0

    def test_649_rub(self):
        """Basic plan: 649₽ × 73 = 47377 ≈ 108000 / ~2.27 factor (just test conversion)."""
        result = rub_to_seconds(649.0)
        assert result == int(649.0 * RUB_TO_SECONDS)


class TestReferralBonus:
    def test_20_percent(self):
        bonus = calculate_referral_bonus_rub(649.0)
        assert abs(bonus - 129.8) < 0.01

    def test_zero_payment(self):
        assert calculate_referral_bonus_rub(0.0) == 0.0

    def test_percentage_correctness(self):
        amount = 1000.0
        bonus = calculate_referral_bonus_rub(amount)
        assert abs(bonus - amount * REFERRAL_BONUS_PERCENT) < 0.001
