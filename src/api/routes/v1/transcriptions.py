"""Web transcription: file upload + URL + status polling."""
import asyncio
import math
import tempfile
import uuid
from pathlib import Path

import aiofiles
import boto3
from botocore.client import Config
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user, get_db
from src.config import settings
from src.db.models.transcription import Transcription
from src.db.models.user import User
from src.db.repositories.transcription import (
    create_transcription,
    get_transcription,
)
from src.services.billing import check_can_transcribe
from src.services.storage import get_presigned_url
from src.utils.logging import get_logger

router = APIRouter(prefix="/transcriptions", tags=["transcriptions"])
logger = get_logger(__name__)

_AUDIO_MIME = frozenset(
    [
        "audio/mpeg", "audio/mp3", "audio/mp4", "audio/ogg", "audio/wav",
        "audio/webm", "audio/aac", "audio/flac", "audio/x-flac",
        "audio/m4a", "audio/x-m4a",
    ]
)
_VIDEO_MIME = frozenset(
    ["video/mp4", "video/mpeg", "video/quicktime", "video/webm", "video/x-matroska"]
)


def _t_to_dict(t: Transcription) -> dict:
    return {
        "id": t.id,
        "status": t.status,
        "source_type": t.source_type,
        "file_name": t.file_name,
        "duration_seconds": t.duration_seconds,
        "seconds_charged": t.seconds_charged,
        "is_free": t.is_free,
        "language": t.language,
        "result_text": t.result_text,
        "summary_text": t.summary_text,
        "error_message": t.error_message,
        "s3_key": t.s3_key,
        "created_at": t.created_at.isoformat(),
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }


@router.get("")
async def list_my_transcriptions(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    total = (
        await session.scalar(
            select(func.count(Transcription.id)).where(Transcription.user_id == user.id)
        )
    ) or 0
    offset = (page - 1) * per_page
    rows = (
        await session.execute(
            select(Transcription)
            .where(Transcription.user_id == user.id)
            .order_by(Transcription.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
    ).scalars().all()
    return {
        "items": [_t_to_dict(t) for t in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, math.ceil(total / per_page)),
    }


@router.get("/{transcription_id}")
async def get_my_transcription(
    transcription_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    t = await get_transcription(transcription_id, session)
    if not t or t.user_id != user.id:
        raise HTTPException(status_code=404, detail="Transcription not found")
    return _t_to_dict(t)


@router.get("/{transcription_id}/download")
async def get_download_url(
    transcription_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    t = await get_transcription(transcription_id, session)
    if not t or t.user_id != user.id:
        raise HTTPException(status_code=404, detail="Transcription not found")
    if not t.s3_key:
        raise HTTPException(status_code=404, detail="File not available")
    url = await get_presigned_url(t.s3_key)
    return {"url": url}


@router.post("/upload", status_code=202)
async def upload_transcription(
    file: UploadFile = File(...),
    language: str = Form(default="ru"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Accept an audio/video file upload and queue a transcription job."""
    content_type = (file.content_type or "").lower()
    if content_type not in _AUDIO_MIME | _VIDEO_MIME:
        raise HTTPException(status_code=422, detail=f"Unsupported file type: {content_type}")

    can, reason = await check_can_transcribe(user)
    if not can:
        raise HTTPException(status_code=402, detail=reason)

    suffix = Path(file.filename or "upload").suffix or ".mp3"
    tmp = Path(tempfile.mktemp(suffix=suffix))
    try:
        size = 0
        async with aiofiles.open(tmp, "wb") as fh:
            while chunk := await file.read(1024 * 1024):  # 1 MB chunks
                size += len(chunk)
                if size > settings.MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {settings.MAX_UPLOAD_BYTES // (1024*1024)} MB limit",
                    )
                await fh.write(chunk)

        # Upload to S3 under uploads/ prefix.
        s3_key = f"uploads/{uuid.uuid4()}{suffix}"

        def _upload():
            client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                config=Config(signature_version="s3v4"),
            )
            client.upload_file(str(tmp), settings.S3_BUCKET, s3_key)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _upload)

    finally:
        tmp.unlink(missing_ok=True)

    source_type = "video" if content_type in _VIDEO_MIME else "audio"
    is_free = user.free_uses_left > 0

    t = await create_transcription(
        user_id=user.id,
        source_type=source_type,
        session=session,
        source_url=f"s3://{s3_key}",
        file_name=file.filename,
        file_size_bytes=size,
        is_free=is_free,
    )

    if is_free:
        user.free_uses_left -= 1
        await session.commit()

    from src.worker.tasks.transcription import transcribe_task

    task = transcribe_task.apply_async(
        kwargs={
            "transcription_id": t.id,
            "user_id": user.id,
            "source_type": source_type,
            "source_url": f"s3://{s3_key}",
        },
        queue="transcription",
    )

    # Store celery task id.
    t.celery_task_id = task.id
    await session.commit()

    return {"transcription_id": t.id, "status": "pending"}


class UrlBody(BaseModel):
    url: str
    language: str = "ru"


@router.post("/url", status_code=202)
async def url_transcription(
    body: UrlBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Queue transcription for a remote URL (YouTube, Rutube, direct file…)."""
    from src.utils.validators import is_allowed_url, is_safe_remote_url

    if not is_allowed_url(body.url):
        raise HTTPException(status_code=422, detail="URL not allowed")
    if not is_safe_remote_url(body.url):
        raise HTTPException(status_code=422, detail="URL resolves to a private/unsafe host")

    can, reason = await check_can_transcribe(user)
    if not can:
        raise HTTPException(status_code=402, detail=reason)

    # Detect source type from URL.
    url_lower = body.url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        source_type = "youtube"
    elif "rutube.ru" in url_lower:
        source_type = "rutube"
    elif "vk.com" in url_lower or "vkvideo.ru" in url_lower:
        source_type = "vk"
    else:
        source_type = "url"

    is_free = user.free_uses_left > 0
    t = await create_transcription(
        user_id=user.id,
        source_type=source_type,
        session=session,
        source_url=body.url,
        is_free=is_free,
    )

    if is_free:
        user.free_uses_left -= 1
        await session.commit()

    from src.worker.tasks.transcription import transcribe_task

    task = transcribe_task.apply_async(
        kwargs={
            "transcription_id": t.id,
            "user_id": user.id,
            "source_type": source_type,
            "source_url": body.url,
        },
        queue="transcription",
    )
    t.celery_task_id = task.id
    await session.commit()

    return {"transcription_id": t.id, "status": "pending"}
