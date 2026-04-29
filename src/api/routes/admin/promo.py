"""Admin promo-code CRUD."""
import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db, require_admin
from src.db.models.promo_code import PromoCode

router = APIRouter(prefix="/promo-codes", tags=["admin-promo"])


def _pc_to_dict(p: PromoCode) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "type": p.type,
        "value": p.value,
        "max_uses": p.max_uses,
        "used_count": p.used_count,
        "expires_at": p.expires_at.isoformat() if p.expires_at else None,
        "is_active": p.is_active,
        "created_at": p.created_at.isoformat(),
    }


@router.get("")
async def list_promo_codes(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    total = (await session.scalar(select(func.count(PromoCode.id)))) or 0
    offset = (page - 1) * per_page
    rows = (
        await session.execute(
            select(PromoCode).order_by(PromoCode.created_at.desc()).offset(offset).limit(per_page)
        )
    ).scalars().all()
    return {
        "items": [_pc_to_dict(p) for p in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, math.ceil(total / per_page)),
    }


class PromoCreateBody(BaseModel):
    code: str
    type: str = "free_seconds"
    value: int
    max_uses: Optional[int] = None
    expires_at: Optional[datetime] = None


@router.post("", status_code=201)
async def create_promo_code(
    body: PromoCreateBody,
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    existing = (
        await session.execute(select(PromoCode).where(PromoCode.code == body.code.upper()))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Code already exists")

    p = PromoCode(
        code=body.code.upper(),
        type=body.type,
        value=body.value,
        max_uses=body.max_uses,
        expires_at=body.expires_at,
    )
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return _pc_to_dict(p)


class PromoPatchBody(BaseModel):
    is_active: Optional[bool] = None
    max_uses: Optional[int] = None


@router.patch("/{promo_id}")
async def patch_promo_code(
    promo_id: int,
    body: PromoPatchBody,
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    p = (
        await session.execute(select(PromoCode).where(PromoCode.id == promo_id))
    ).scalar_one_or_none()
    if not p:
        raise HTTPException(status_code=404, detail="Promo code not found")

    if body.is_active is not None:
        p.is_active = body.is_active
    if body.max_uses is not None:
        p.max_uses = body.max_uses

    await session.commit()
    await session.refresh(p)
    return _pc_to_dict(p)
