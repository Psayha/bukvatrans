"""Web promo code redemption."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db
from src.db.models.promo_code import PromoCode, PromoCodeUse
from src.db.models.user import User

router = APIRouter(prefix="/promo", tags=["promo"])


class PromoBody(BaseModel):
    code: str


@router.post("")
async def apply_promo(
    body: PromoBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    code = body.code.strip().upper()
    pc = (
        await session.execute(select(PromoCode).where(PromoCode.code == code))
    ).scalar_one_or_none()

    if not pc or not pc.is_active:
        raise HTTPException(status_code=400, detail="Invalid or inactive promo code")
    if pc.expires_at and pc.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Promo code has expired")
    if pc.max_uses and pc.used_count >= pc.max_uses:
        raise HTTPException(status_code=400, detail="Promo code usage limit reached")

    already_used = (
        await session.execute(
            select(PromoCodeUse).where(
                PromoCodeUse.promo_code_id == pc.id,
                PromoCodeUse.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if already_used:
        raise HTTPException(status_code=400, detail="You have already used this code")

    seconds_added = pc.value if pc.type == "free_seconds" else 0
    if seconds_added <= 0:
        raise HTTPException(status_code=400, detail="Unsupported promo code type")

    user.balance_seconds += seconds_added
    pc.used_count += 1
    session.add(PromoCodeUse(promo_code_id=pc.id, user_id=user.id))
    await session.commit()

    return {
        "ok": True,
        "seconds_added": seconds_added,
        "new_balance_seconds": user.balance_seconds,
    }
