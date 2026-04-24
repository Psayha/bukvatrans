"""Gamification utils — level tiers, progress bars, saved-time phrasing.

Pure functions; no I/O, no async — fast unit tests.
"""
from src.utils.gamification import (
    format_level_line,
    level_for,
    progress_bar,
    saved_time_phrase,
)


class TestLevelFor:
    def test_zero_is_novice(self):
        info = level_for(0)
        assert info.name == "Новичок"
        assert info.emoji == "🌱"

    def test_just_below_active_threshold_still_novice(self):
        info = level_for(599)  # threshold is 600
        assert info.name == "Новичок"

    def test_exactly_on_threshold_promotes(self):
        info = level_for(600)
        assert info.name == "Активный"

    def test_expert_threshold(self):
        info = level_for(3_600)
        assert info.name == "Знаток"

    def test_master_threshold(self):
        info = level_for(36_000)
        assert info.name == "Мастер"

    def test_deep_past_master_stays_master(self):
        info = level_for(100_000_000)
        assert info.name == "Мастер"
        assert info.progress_ratio == 1.0

    def test_progress_ratio_midway(self):
        # Between Активный (600) and Знаток (3600) — halfway is 2100.
        info = level_for(2_100)
        assert 0.45 < info.progress_ratio < 0.55

    def test_progress_clamped_to_unit_interval(self):
        for seconds in (-100, 0, 600, 1_000_000):
            info = level_for(seconds)
            assert 0.0 <= info.progress_ratio <= 1.0


class TestProgressBar:
    def test_empty_bar_at_zero(self):
        bar = progress_bar(0.0, width=10)
        assert bar.count("▰") == 0
        assert bar.count("▱") == 10

    def test_full_bar_at_one(self):
        bar = progress_bar(1.0, width=10)
        assert bar.count("▰") == 10
        assert bar.count("▱") == 0

    def test_half_bar(self):
        bar = progress_bar(0.5, width=10)
        # 0.5 * 10 = 5 filled segments.
        assert bar.count("▰") == 5
        assert bar.count("▱") == 5

    def test_width_respected(self):
        for width in (1, 3, 5, 20):
            bar = progress_bar(0.3, width=width)
            assert len(bar) == width

    def test_out_of_range_clamped(self):
        for ratio in (-5.0, 1.5, 99.0):
            bar = progress_bar(ratio, width=4)
            assert bar in {"▰▰▰▰", "▱▱▱▱"}


class TestFormatLevelLine:
    def test_contains_name_and_emoji(self):
        line = format_level_line(0)
        assert "Новичок" in line
        assert "🌱" in line

    def test_master_says_max(self):
        line = format_level_line(100_000)
        assert "Мастер" in line
        assert "максимальный" in line.lower() or "max" in line.lower()

    def test_shows_remaining_to_next(self):
        # User is Активный (600s), next threshold is Знаток (3600s),
        # so remaining is 3000s = 50 min.
        line = format_level_line(600)
        assert "Активный" in line
        assert "мин" in line or "час" in line


class TestSavedTimePhrase:
    def test_tiny_amount_no_hint(self):
        # Savings below 60s hit the fallback branch with the raw number.
        phrase = saved_time_phrase(30)
        assert "сек" in phrase

    def test_medium_amount_has_hint(self):
        phrase = saved_time_phrase(1_000)
        # 2/3 * 1000 ≈ 666s = ~11 min → falls under the 300s bucket.
        assert "кофе" in phrase.lower() or "мин" in phrase

    def test_big_amount_mentions_break_or_workday(self):
        phrase = saved_time_phrase(60_000)
        # 2/3 * 60000 = 40000s > 21600 → workday hint.
        assert "рабоч" in phrase.lower() or "ч" in phrase
