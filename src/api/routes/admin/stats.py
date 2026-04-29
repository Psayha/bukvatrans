"""Admin dashboard statistics."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import cast, Date, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db, require_admin
from src.db.models.subscription import Subscription
from src.db.models.transaction import Transaction
from src.db.models.transcription import Transcription
from src.db.models.user import User

router = APIRouter(prefix="/stats", tags=["admin-stats"])


@router.get("")
async def get_stats(
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    async def cnt(stmt) -> int:
        return (await session.scalar(stmt)) or 0

    total_users = await cnt(select(func.count(User.id)))
    banned_users = await cnt(select(func.count(User.id)).where(User.is_banned.is_(True)))
    new_24h = await cnt(select(func.count(User.id)).where(User.created_at >= day_ago))
    new_7d = await cnt(select(func.count(User.id)).where(User.created_at >= week_ago))
    new_30d = await cnt(select(func.count(User.id)).where(User.created_at >= month_ago))
    active_subs = await cnt(
        select(func.count(distinct(Subscription.user_id))).where(
            Subscription.status == "active",
            Subscription.expires_at > now,
        )
    )

    done_24h = await cnt(
        select(func.count(Transcription.id)).where(
            Transcription.status == "done", Transcription.created_at >= day_ago
        )
    )
    failed_24h = await cnt(
        select(func.count(Transcription.id)).where(
            Transcription.status == "failed", Transcription.created_at >= day_ago
        )
    )
    seconds_24h = await cnt(
        select(func.coalesce(func.sum(Transcription.duration_seconds), 0)).where(
            Transcription.status == "done", Transcription.created_at >= day_ago
        )
    )
    done_7d = await cnt(
        select(func.count(Transcription.id)).where(
            Transcription.status == "done", Transcription.created_at >= week_ago
        )
    )
    seconds_7d = await cnt(
        select(func.coalesce(func.sum(Transcription.duration_seconds), 0)).where(
            Transcription.status == "done", Transcription.created_at >= week_ago
        )
    )

    def _rev_stmt(since):
        return select(
            func.count(Transaction.id),
            func.coalesce(func.sum(Transaction.amount_rub), 0),
        ).where(
            Transaction.status == "success",
            Transaction.type.in_(["subscription", "topup"]),
            Transaction.created_at >= since,
        )

    cnt_24h, sum_24h = (await session.execute(_rev_stmt(day_ago))).one()
    cnt_7d, sum_7d = (await session.execute(_rev_stmt(week_ago))).one()
    cnt_30d, sum_30d = (await session.execute(_rev_stmt(month_ago))).one()

    return {
        "users": {
            "total": total_users,
            "banned": banned_users,
            "new_24h": new_24h,
            "new_7d": new_7d,
            "new_30d": new_30d,
            "active_subscribers": active_subs,
        },
        "transcriptions": {
            "done_24h": done_24h,
            "failed_24h": failed_24h,
            "hours_24h": round(seconds_24h / 3600, 1),
            "done_7d": done_7d,
            "hours_7d": round(seconds_7d / 3600, 1),
        },
        "revenue": {
            "count_24h": cnt_24h,
            "sum_24h": float(sum_24h),
            "count_7d": cnt_7d,
            "sum_7d": float(sum_7d),
            "count_30d": cnt_30d,
            "sum_30d": float(sum_30d),
        },
    }


@router.get("/revenue")
async def get_revenue_chart(
    days: int = Query(default=30, ge=1, le=365),
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(
            cast(Transaction.created_at, Date).label("date"),
            func.count(Transaction.id).label("count"),
            func.coalesce(func.sum(Transaction.amount_rub), 0).label("amount"),
        )
        .where(
            Transaction.status == "success",
            Transaction.type.in_(["subscription", "topup"]),
            Transaction.created_at >= since,
        )
        .group_by(cast(Transaction.created_at, Date))
        .order_by("date")
    )
    rows = (await session.execute(stmt)).all()
    return {
        "data": [
            {"date": str(r.date), "count": r.count, "amount": float(r.amount)}
            for r in rows
        ]
    }


@router.get("/users-growth")
async def get_users_chart(
    days: int = Query(default=30, ge=1, le=365),
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)
    stmt = (
        select(
            cast(User.created_at, Date).label("date"),
            func.count(User.id).label("count"),
        )
        .where(User.created_at >= since)
        .group_by(cast(User.created_at, Date))
        .order_by("date")
    )
    rows = (await session.execute(stmt)).all()
    return {"data": [{"date": str(r.date), "count": r.count} for r in rows]}
