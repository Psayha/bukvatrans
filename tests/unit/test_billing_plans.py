"""Tests for billing plans and topup options."""
from src.services.billing import (
    FREE_USES_PER_MONTH,
    PLANS,
    REFERRAL_FREE_MONTH_THRESHOLD,
    TOPUP_OPTIONS,
)


class TestPlansConfig:
    def test_all_plans_exist(self):
        for key in ("unlimited_7d", "unlimited_30d", "unlimited_180d"):
            assert key in PLANS

    def test_all_plans_unlimited(self):
        # Post-redesign, every plan is unlimited; only the period differs.
        for key, plan in PLANS.items():
            assert plan["seconds"] == -1, f"{key} should be unlimited"

    def test_plan_has_label(self):
        for plan in PLANS.values():
            assert "label" in plan and plan["label"]

    def test_prices(self):
        assert PLANS["unlimited_7d"]["price_rub"] == 249.0
        assert PLANS["unlimited_30d"]["price_rub"] == 549.0
        assert PLANS["unlimited_180d"]["price_rub"] == 2499.0

    def test_periods(self):
        assert PLANS["unlimited_7d"]["period_days"] == 7
        assert PLANS["unlimited_30d"]["period_days"] == 30
        assert PLANS["unlimited_180d"]["period_days"] == 180

    def test_exactly_one_recommended(self):
        flagged = [k for k, p in PLANS.items() if p.get("recommended")]
        assert flagged == ["unlimited_30d"]

    def test_monthly_cheaper_per_day_than_weekly(self):
        per_day_weekly = PLANS["unlimited_7d"]["price_rub"] / 7
        per_day_monthly = PLANS["unlimited_30d"]["price_rub"] / 30
        assert per_day_monthly < per_day_weekly

    def test_half_year_cheaper_per_day_than_monthly(self):
        per_day_monthly = PLANS["unlimited_30d"]["price_rub"] / 30
        per_day_half = PLANS["unlimited_180d"]["price_rub"] / 180
        assert per_day_half < per_day_monthly


class TestTopupOptions:
    def test_all_options_exist(self):
        for key in ("topup_99", "topup_299", "topup_499"):
            assert key in TOPUP_OPTIONS

    def test_topup_99_price(self):
        assert TOPUP_OPTIONS["topup_99"]["price_rub"] == 99.0

    def test_topup_99_seconds(self):
        """99₽ → 2 hours = 7200 seconds."""
        assert TOPUP_OPTIONS["topup_99"]["seconds"] == 7200

    def test_topup_299_seconds(self):
        """299₽ → 7 hours = 25200 seconds."""
        assert TOPUP_OPTIONS["topup_299"]["seconds"] == 25200

    def test_topup_499_seconds(self):
        """499₽ → 12 hours = 43200 seconds."""
        assert TOPUP_OPTIONS["topup_499"]["seconds"] == 43200

    def test_larger_topup_better_value(self):
        """Higher-priced topups should give more seconds per ruble."""
        rate_99 = TOPUP_OPTIONS["topup_99"]["seconds"] / TOPUP_OPTIONS["topup_99"]["price_rub"]
        rate_299 = TOPUP_OPTIONS["topup_299"]["seconds"] / TOPUP_OPTIONS["topup_299"]["price_rub"]
        rate_499 = TOPUP_OPTIONS["topup_499"]["seconds"] / TOPUP_OPTIONS["topup_499"]["price_rub"]
        assert rate_299 >= rate_99
        assert rate_499 >= rate_299


class TestBusinessConstants:
    def test_free_uses_per_month(self):
        assert FREE_USES_PER_MONTH == 3

    def test_referral_threshold_positive(self):
        assert REFERRAL_FREE_MONTH_THRESHOLD >= 1
