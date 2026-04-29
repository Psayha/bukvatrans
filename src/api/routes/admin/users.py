"""Admin user management."""
import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db, require_admin
from src.db.models.subscription import Subscription
from src.db.models.transaction import Transaction
from src.db.models.transcription import Transcription
from src.db.models.user import User

router = APIRouter(prefix="/users", tags=["admin-users"])


def _active_sub(user: User) -> Optional[Subscription]:
    now = datetime.now(timezone.utc)
    for s in user.subscriptions:
        exp = s.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if s.status == "active" and exp > now:
            return s
    return None


def _user_to_dict(user: User) -> dict:
    sub = _active_sub(user)
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "balance_seconds": user.balance_seconds,
        "free_uses_left": user.free_uses_left,
        "is_banned": user.is_banned,
        "is_admin": user.is_admin,
        "has_active_subscription": sub is not None,
        "subscription_plan": sub.plan if sub else None,
        "subscription_expires_at": sub.expires_at.isoformat() if sub else None,
        "created_at": user.created_at.isoformat(),
        "last_seen_at": user.last_seen_at.isoformat() if user.last_seen_at else None,
    }


@router.get("")
async def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    q: str = Query(default=""),
    banned: Optional[bool] = Query(default=None),
    has_subscription: Optional[bool] = Query(default=None),
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(User)
    count_stmt = select(func.count(User.id))

    if q:
        filters = [
            User.username.ilike(f"%{q}%"),
            User.first_name.ilike(f"%{q}%"),
        ]
        if q.lstrip("-").isdigit():
            filters.append(User.id == int(q))
        clause = or_(*filters)
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)

    if banned is not None:
        stmt = stmt.where(User.is_banned.is_(banned))
        count_stmt = count_stmt.where(User.is_banned.is_(banned))

    if has_subscription is not None:
        now = datetime.utcnow()
        active_sub_exists = (
            select(Subscription.id)
            .where(
                Subscription.user_id == User.id,
                Subscription.status == "active",
                Subscription.expires_at > now,
            )
            .exists()
        )
        if has_subscription:
            stmt = stmt.where(active_sub_exists)
            count_stmt = count_stmt.where(active_sub_exists)
        else:
            stmt = stmt.where(~active_sub_exists)
            count_stmt = count_stmt.where(~active_sub_exists)

    total = (await session.scalar(count_stmt)) or 0
    offset = (page - 1) * per_page
    stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(per_page)
    users = (await session.execute(stmt)).scalars().all()

    return {
        "items": [_user_to_dict(u) for u in users],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, math.ceil(total / per_page)),
    }


@router.get("/{user_id}")
async def get_user_detail(
    user_id: int,
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    tx_count = (
        await session.scalar(
            select(func.count(Transcription.id)).where(
                Transcription.user_id == user_id, Transcription.status == "done"
            )
        )
    ) or 0
    total_seconds = (
        await session.scalar(
            select(func.coalesce(func.sum(Transcription.duration_seconds), 0)).where(
                Transcription.user_id == user_id, Transcription.status == "done"
            )
        )
    ) or 0
    total_spent = (
        await session.scalar(
            select(func.coalesce(func.sum(Transaction.amount_rub), 0)).where(
                Transaction.user_id == user_id, Transaction.status == "success"
            )
        )
    ) or 0

    recent_transcriptions = (
        await session.execute(
            select(Transcription)
            .where(Transcription.user_id == user_id)
            .order_by(Transcription.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    recent_transactions = (
        await session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .limit(20)
        )
    ).scalars().all()

    base = _user_to_dict(user)
    base.update(
        {
            "consent_at": user.consent_at.isoformat() if user.consent_at else None,
            "referrer_id": user.referrer_id,
            "transcriptions_count": tx_count,
            "total_seconds_transcribed": total_seconds,
            "total_spent_rub": float(total_spent),
            "subscriptions": [
                {
                    "id": s.id,
                    "plan": s.plan,
                    "status": s.status,
                    "started_at": s.started_at.isoformat(),
                    "expires_at": s.expires_at.isoformat(),
                }
                for s in sorted(user.subscriptions, key=lambda s: s.started_at, reverse=True)
            ],
            "recent_transcriptions": [
                {
                    "id": t.id,
                    "status": t.status,
                    "source_type": t.source_type,
                    "file_name": t.file_name,
                    "duration_seconds": t.duration_seconds,
                    "seconds_charged": t.seconds_charged,
                    "is_free": t.is_free,
                    "created_at": t.created_at.isoformat(),
                }
                for t in recent_transcriptions
            ],
            "recent_transactions": [
                {
                    "id": tr.id,
                    "type": tr.type,
                    "amount_rub": float(tr.amount_rub) if tr.amount_rub else None,
                    "seconds_added": tr.seconds_added,
                    "status": tr.status,
                    "created_at": tr.created_at.isoformat(),
                }
                for tr in recent_transactions
            ],
        }
    )
    return base


class UserPatchBody(BaseModel):
    is_banned: Optional[bool] = None
    is_admin: Optional[bool] = None
    add_balance_seconds: Optional[int] = None


@router.patch("/{user_id}")
async def patch_user(
    user_id: int,
    body: UserPatchBody,
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.is_banned is not None:
        user.is_banned = body.is_banned
    if body.is_admin is not None:
        user.is_admin = body.is_admin
    if body.add_balance_seconds is not None:
        user.balance_seconds = max(0, user.balance_seconds + body.add_balance_seconds)

    await session.commit()
    await session.refresh(user)
    return _user_to_dict(user)
