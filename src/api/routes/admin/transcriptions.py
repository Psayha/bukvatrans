"""Admin transcription browser."""
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db, require_admin
from src.db.models.transcription import Transcription
from src.db.models.user import User

router = APIRouter(prefix="/transcriptions", tags=["admin-transcriptions"])


def _t_to_dict(t: Transcription, username: Optional[str] = None) -> dict:
    return {
        "id": t.id,
        "user_id": t.user_id,
        "user_display": username or str(t.user_id),
        "status": t.status,
        "source_type": t.source_type,
        "file_name": t.file_name,
        "file_size_bytes": t.file_size_bytes,
        "duration_seconds": t.duration_seconds,
        "seconds_charged": t.seconds_charged,
        "is_free": t.is_free,
        "language": t.language,
        "error_message": t.error_message,
        "created_at": t.created_at.isoformat(),
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }


@router.get("")
async def list_transcriptions(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    status: Optional[str] = Query(default=None),
    user_id: Optional[int] = Query(default=None),
    source_type: Optional[str] = Query(default=None),
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(Transcription)
    count_stmt = select(func.count(Transcription.id))

    if status and status != "all":
        stmt = stmt.where(Transcription.status == status)
        count_stmt = count_stmt.where(Transcription.status == status)
    if user_id:
        stmt = stmt.where(Transcription.user_id == user_id)
        count_stmt = count_stmt.where(Transcription.user_id == user_id)
    if source_type:
        stmt = stmt.where(Transcription.source_type == source_type)
        count_stmt = count_stmt.where(Transcription.source_type == source_type)

    total = (await session.scalar(count_stmt)) or 0
    offset = (page - 1) * per_page
    stmt = stmt.order_by(Transcription.created_at.desc()).offset(offset).limit(per_page)
    rows = (await session.execute(stmt)).scalars().all()

    # Batch load usernames
    user_ids = list({r.user_id for r in rows})
    usernames: dict[int, str] = {}
    if user_ids:
        users = (
            await session.execute(select(User).where(User.id.in_(user_ids)))
        ).scalars().all()
        usernames = {u.id: (u.username or u.first_name or str(u.id)) for u in users}

    return {
        "items": [_t_to_dict(t, usernames.get(t.user_id)) for t in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, math.ceil(total / per_page)),
    }


@router.get("/{transcription_id}")
async def get_transcription(
    transcription_id: str,
    _=Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    t = (
        await session.execute(
            select(Transcription).where(Transcription.id == transcription_id)
        )
    ).scalar_one_or_none()
    if not t:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Transcription not found")

    user = (
        await session.execute(select(User).where(User.id == t.user_id))
    ).scalar_one_or_none()
    d = _t_to_dict(t, user.username or user.first_name if user else None)
    d["result_text"] = t.result_text
    d["summary_text"] = t.summary_text
    d["source_url"] = t.source_url
    return d
