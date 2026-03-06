from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.transcription import Transcription


async def create_transcription(
    user_id: int,
    source_type: str,
    session: AsyncSession,
    source_url: Optional[str] = None,
    file_name: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
    file_unique_id: Optional[str] = None,
    is_free: bool = False,
) -> Transcription:
    t = Transcription(
        user_id=user_id,
        source_type=source_type,
        source_url=source_url,
        file_name=file_name,
        file_size_bytes=file_size_bytes,
        file_unique_id=file_unique_id,
        is_free=is_free,
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t


async def get_transcription(transcription_id: str, session: AsyncSession) -> Optional[Transcription]:
    result = await session.execute(
        select(Transcription).where(Transcription.id == transcription_id)
    )
    return result.scalar_one_or_none()


async def get_cached_transcription(
    file_unique_id: str, session: AsyncSession
) -> Optional[Transcription]:
    """Return a completed transcription for the same file within last 24 hours."""
    since = datetime.utcnow() - timedelta(hours=24)
    result = await session.execute(
        select(Transcription).where(
            Transcription.file_unique_id == file_unique_id,
            Transcription.status == "done",
            Transcription.created_at >= since,
        )
    )
    return result.scalar_one_or_none()


async def get_user_transcriptions(
    user_id: int, session: AsyncSession, limit: int = 10
) -> list[Transcription]:
    result = await session.execute(
        select(Transcription)
        .where(Transcription.user_id == user_id)
        .order_by(Transcription.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def update_transcription_status(
    transcription_id: str,
    status: str,
    session: AsyncSession,
    result_text: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    seconds_charged: Optional[int] = None,
    error_message: Optional[str] = None,
    celery_task_id: Optional[str] = None,
    s3_key: Optional[str] = None,
) -> Optional[Transcription]:
    t = await get_transcription(transcription_id, session)
    if not t:
        return None
    t.status = status
    if result_text is not None:
        t.result_text = result_text
    if duration_seconds is not None:
        t.duration_seconds = duration_seconds
    if seconds_charged is not None:
        t.seconds_charged = seconds_charged
    if error_message is not None:
        t.error_message = error_message
    if celery_task_id is not None:
        t.celery_task_id = celery_task_id
    if s3_key is not None:
        t.s3_key = s3_key
    if status == "done":
        t.completed_at = datetime.utcnow()
    await session.commit()
    await session.refresh(t)
    return t
