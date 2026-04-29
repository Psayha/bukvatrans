"""Level system + motivational "time saved" phrasing.

A pure helper module — no DB, no I/O. Feed it total-transcribed-seconds,
get back a {level_name, emoji, progress} triplet and a humanising hint
about the time saved.
"""
from dataclasses import dataclass

from src.bot.texts.ru import LEVELS, SAVED_TIME_HINTS


@dataclass(frozen=True)
class LevelInfo:
    name: str
    emoji: str
    current: int            # current level's floor in seconds
    next_threshold: int     # next level's floor (or None if maxed)
    progress_ratio: float   # 0..1 within the current segment


def level_for(total_seconds: int) -> LevelInfo:
    """Resolve the user's level.

    Ties: if the user is exactly on a boundary, they belong to the HIGHER
    level ("earns" it immediately).
    """
    picked = LEVELS[0]
    picked_idx = 0
    for idx, (name, threshold, emoji) in enumerate(LEVELS):
        if total_seconds >= threshold:
            picked = (name, threshold, emoji)
            picked_idx = idx
    name, threshold, emoji = picked
    next_threshold = (
        LEVELS[picked_idx + 1][1] if picked_idx + 1 < len(LEVELS) else -1
    )
    if next_threshold <= threshold:
        progress = 1.0
    else:
        segment = next_threshold - threshold
        progress = max(
            0.0, min(1.0, (total_seconds - threshold) / segment)
        )
    return LevelInfo(
        name=name,
        emoji=emoji,
        current=threshold,
        next_threshold=next_threshold,
        progress_ratio=progress,
    )


def progress_bar(ratio: float, width: int = 10) -> str:
    """ASCII progress bar: `▰▰▰▱▱▱▱▱▱▱` style."""
    ratio = max(0.0, min(1.0, ratio))
    filled = int(round(ratio * width))
    return "▰" * filled + "▱" * (width - filled)


def format_level_line(total_seconds: int) -> str:
    """Compact multi-line block for `/profile` / `/settings` headers."""
    info = level_for(total_seconds)
    bar = progress_bar(info.progress_ratio)
    if info.next_threshold < 0:
        tail = "— максимальный уровень"
    else:
        tail = f"до следующего: {_format_seconds_short(info.next_threshold - total_seconds)}"
    return f"{info.emoji} <b>{info.name}</b> {bar} {tail}"


def saved_time_phrase(total_seconds: int) -> str:
    """Return a short phrase describing how much time the user saved.

    Reading is ~3x faster than listening, so saved ≈ 2/3 of total.
    Threshold table picks the fitting vibe.
    """
    saved = int(total_seconds * 2 / 3)
    phrase = None
    for threshold, hint in SAVED_TIME_HINTS:
        if saved >= threshold:
            phrase = hint
    if phrase is None:
        return _format_seconds_short(saved)
    return f"{_format_seconds_short(saved)} {phrase}"


def get_level_info(user) -> dict:
    """Return a JSON-serialisable gamification block for the API profile response."""
    info = level_for(user.balance_seconds)
    return {
        "level_name": info.name,
        "level_emoji": info.emoji,
        "progress_ratio": info.progress_ratio,
        "current_threshold": info.current,
        "next_threshold": info.next_threshold if info.next_threshold >= 0 else None,
        "saved_time": saved_time_phrase(user.balance_seconds),
    }


def _format_seconds_short(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} сек"
    if seconds < 3600:
        return f"{seconds // 60} мин"
    hours = seconds // 3600
    remainder_min = (seconds % 3600) // 60
    if remainder_min == 0:
        return f"{hours} ч"
    return f"{hours} ч {remainder_min} мин"
