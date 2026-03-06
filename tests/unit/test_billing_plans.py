"""Tests for billing plans and topup options."""
import pytest
from src.services.billing import PLANS, TOPUP_OPTIONS, rub_to_seconds


class TestPlansConfig:
    def test_all_plans_exist(self):
        for key in ("basic_monthly", "basic_yearly", "pro_monthly", "pro_yearly"):
            assert key in PLANS

    def test_basic_monthly_price(self):
        assert PLANS["basic_monthly"]["price_rub"] == 649.0

    def test_basic_yearly_price(self):
        assert PLANS["basic_yearly"]["price_rub"] == 3890.0

    def test_pro_monthly_unlimited(self):
        assert PLANS["pro_monthly"]["seconds"] == -1

    def test_pro_yearly_unlimited(self):
        assert PLANS["pro_yearly"]["seconds"] == -1

    def test_basic_monthly_seconds(self):
        """108000 seconds = 30 hours."""
        assert PLANS["basic_monthly"]["seconds"] == 108_000

    def test_basic_monthly_period(self):
        assert PLANS["basic_monthly"]["period_days"] == 30

    def test_basic_yearly_period(self):
        assert PLANS["basic_yearly"]["period_days"] == 365

    def test_yearly_cheaper_per_month(self):
        """Yearly plan should be cheaper per month than monthly."""
        monthly = PLANS["basic_monthly"]["price_rub"]
        yearly_per_month = PLANS["basic_yearly"]["price_rub"] / 12
        assert yearly_per_month < monthly


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
