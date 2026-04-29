"""Admin transaction / revenue browser."""
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db, require_admin
from src.db.models.transaction import Transaction
from src.db.models.user import User

router = APIRouter(prefix="/transactions", tags=["admin-transactions"])


@router.get("")
async def list_transactions(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    tx_type: Optional[str] = Query(default=None, alias="type"),
    status: Optional[str] = Query(default=None),
    user_id: Optional[int] = Query(default=None),
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(Transaction)
    count_stmt = select(func.count(Transaction.id))

    if tx_type:
        stmt = stmt.where(Transaction.type == tx_type)
        count_stmt = count_stmt.where(Transaction.type == tx_type)
    if status:
        stmt = stmt.where(Transaction.status == status)
        count_stmt = count_stmt.where(Transaction.status == status)
    if user_id:
        stmt = stmt.where(Transaction.user_id == user_id)
        count_stmt = count_stmt.where(Transaction.user_id == user_id)

    total = (await session.scalar(count_stmt)) or 0
    offset = (page - 1) * per_page
    stmt = stmt.order_by(Transaction.created_at.desc()).offset(offset).limit(per_page)
    rows = (await session.execute(stmt)).scalars().all()

    user_ids = list({r.user_id for r in rows})
    usernames: dict[int, str] = {}
    if user_ids:
        users = (
            await session.execute(select(User).where(User.id.in_(user_ids)))
        ).scalars().all()
        usernames = {u.id: (u.username or u.first_name or str(u.id)) for u in users}

    return {
        "items": [
            {
                "id": t.id,
                "user_id": t.user_id,
                "user_display": usernames.get(t.user_id, str(t.user_id)),
                "type": t.type,
                "amount_rub": float(t.amount_rub) if t.amount_rub else None,
                "seconds_added": t.seconds_added,
                "status": t.status,
                "yukassa_id": t.yukassa_id,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
            }
            for t in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, math.ceil(total / per_page)),
    }
