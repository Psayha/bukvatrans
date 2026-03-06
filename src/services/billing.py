import math
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.db.models.user import User

# Conversion: 1 RUB = 73 seconds (≈ 49 RUB/hour)
RUB_TO_SECONDS = 73
REFERRAL_BONUS_PERCENT = 0.20

PLANS = {
    "basic_monthly": {"price_rub": 649.0, "seconds": 108_000, "period_days": 30},
    "basic_yearly": {"price_rub": 3_890.0, "seconds": 1_296_000, "period_days": 365},
    "pro_monthly": {"price_rub": 1_449.0, "seconds": -1, "period_days": 30},     # unlimited
    "pro_yearly": {"price_rub": 8_690.0, "seconds": -1, "period_days": 365},     # unlimited
}

TOPUP_OPTIONS = {
    "topup_99": {"price_rub": 99.0, "seconds": 7_200},
    "topup_299": {"price_rub": 299.0, "seconds": 25_200},
    "topup_499": {"price_rub": 499.0, "seconds": 43_200},
}


def calculate_charge(duration_seconds: int) -> int:
    """Round up to the nearest full minute and return seconds to charge."""
    if duration_seconds <= 0:
        return 0
    minutes = math.ceil(duration_seconds / 60)
    return minutes * 60


def rub_to_seconds(amount_rub: float) -> int:
    """Convert rubles to seconds at the rate of RUB_TO_SECONDS seconds per ruble."""
    return int(amount_rub * RUB_TO_SECONDS)


def calculate_referral_bonus_rub(payment_amount_rub: float) -> float:
    """Return 20% of payment amount as referral bonus in rubles."""
    return round(payment_amount_rub * REFERRAL_BONUS_PERCENT, 2)


async def check_can_transcribe(
    user: "User", estimated_duration: Optional[int] = None
) -> tuple[bool, str]:
    """
    Check whether a user can start transcription.
    For URL sources estimated_duration is None — only check balance > 0.
    """
    if user.is_banned:
        return False, "Ваш аккаунт заблокирован."

    if user.has_active_unlimited_subscription():
        return True, ""

    if user.free_uses_left > 0:
        return True, ""

    if user.balance_seconds <= 0:
        return False, "Недостаточно баланса. Пополните счёт или оформите подписку."

    if estimated_duration and user.balance_seconds < estimated_duration:
        return (
            False,
            f"Недостаточно баланса. Файл ~{estimated_duration // 60} мин, "
            f"у вас {user.balance_seconds // 60} мин.",
        )

    return True, ""
