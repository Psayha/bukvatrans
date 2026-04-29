"""User profile, balance, subscription info."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db
from src.db.models.user import User
from src.services.billing import FREE_USES_PER_MONTH, PLANS
from src.utils.gamification import get_level_info

router = APIRouter(prefix="/profile", tags=["profile"])


def _active_sub_dict(user: User) -> dict | None:
    now = datetime.now(timezone.utc)
    for s in user.subscriptions:
        exp = s.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if s.status == "active" and exp > now:
            plan_info = PLANS.get(s.plan, {})
            return {
                "plan": s.plan,
                "label": plan_info.get("label", s.plan),
                "is_unlimited": s.seconds_limit == -1,
                "expires_at": exp.isoformat(),
                "days_left": max(0, (exp - now).days),
            }
    return None


@router.get("")
async def get_profile(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    level = get_level_info(user)
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "email_verified": getattr(user, "email_verified", False),
        "balance_seconds": user.balance_seconds,
        "free_uses_left": user.free_uses_left,
        "free_uses_per_month": FREE_USES_PER_MONTH,
        "active_subscription": _active_sub_dict(user),
        "gamification": level,
        "referral_link": f"https://t.me/{__import__('src.config', fromlist=['settings']).settings.BOT_USERNAME}?start=ref_{user.id}",
    }
