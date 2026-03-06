def format_duration(seconds: int) -> str:
    """Format seconds into human-readable string: '1 ч 23 мин 45 сек'."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts = []
    if hours:
        parts.append(f"{hours} ч")
    if minutes:
        parts.append(f"{minutes} мин")
    if secs or not parts:
        parts.append(f"{secs} сек")
    return " ".join(parts)


def format_balance(seconds: int) -> str:
    """Format balance seconds: '2 ч 30 мин (~150 мин)'."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    total_minutes = seconds // 60
    if hours:
        return f"{hours} ч {minutes} мин (~{total_minutes} мин)"
    return f"{minutes} мин"


def format_price(amount_rub: float) -> str:
    return f"{amount_rub:,.0f}₽".replace(",", " ")
