import pytest
from src.utils.formatters import format_duration, format_balance, format_price


class TestFormatDuration:
    def test_zero(self):
        assert format_duration(0) == "0 сек"

    def test_seconds_only(self):
        assert format_duration(45) == "45 сек"

    def test_minutes_only(self):
        assert format_duration(120) == "2 мин"

    def test_minutes_and_seconds(self):
        assert format_duration(125) == "2 мин 5 сек"

    def test_one_hour(self):
        assert format_duration(3600) == "1 ч"

    def test_one_hour_30_min(self):
        assert format_duration(5400) == "1 ч 30 мин"

    def test_full_time(self):
        # 1h 23m 45s = 3600+1380+45 = 5025
        assert format_duration(5025) == "1 ч 23 мин 45 сек"


class TestFormatBalance:
    def test_zero(self):
        result = format_balance(0)
        assert "0 мин" in result

    def test_one_hour(self):
        result = format_balance(3600)
        assert "1 ч" in result

    def test_90_minutes(self):
        result = format_balance(5400)
        assert "1 ч" in result
        assert "30 мин" in result


class TestFormatPrice:
    def test_649(self):
        assert "649" in format_price(649.0)
        assert "₽" in format_price(649.0)

    def test_large_price(self):
        result = format_price(8690.0)
        assert "8" in result
        assert "₽" in result
