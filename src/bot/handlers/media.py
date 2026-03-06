import tempfile
import uuid
from pathlib import Path
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User
from src.db.repositories.transcription import create_transcription, get_cached_transcription
from src.db.repositories.user import decrement_free_uses
from src.services.billing import check_can_transcribe
from src.utils.validators import validate_file_size, validate_mime_type
from src.bot.texts.ru import (
    PROCESSING, UNSUPPORTED_FORMAT, FILE_TOO_LARGE,
    INSUFFICIENT_BALANCE, TASK_ALREADY_RUNNING,
)
from src.bot.keyboards.inline import subscribe_kb, transcription_result_kb

router = Router()

# Supported Telegram content types
AUDIO_TYPES = {"audio", "voice", "video", "video_note", "document"}


async def _handle_media(
    message: Message,
    user: User,
    session: AsyncSession,
    source_type: str,
    file_id: str,
    file_unique_id: Optional[str],
    file_size: Optional[int],
    mime_type: Optional[str],
    file_name: Optional[str] = None,
) -> None:
    # Validate file size
    if file_size and not validate_file_size(file_size):
        await message.answer(FILE_TOO_LARGE)
        return

    # Validate mime type (skip for voice/video_note — always ogg/mp4)
    if mime_type and source_type not in ("voice", "video_note"):
        if not validate_mime_type(mime_type):
            await message.answer(UNSUPPORTED_FORMAT)
            return

    # Check cache (same file within 24h)
    if file_unique_id:
        cached = await get_cached_transcription(file_unique_id, session)
        if cached and cached.result_text:
            await message.answer(
                f"📋 Ранее расшифрованный текст (кэш):\n\n{cached.result_text[:4000]}",
                parse_mode="HTML",
            )
            return

    # Check balance
    can, reason = await check_can_transcribe(user)
    if not can:
        await message.answer(
            INSUFFICIENT_BALANCE.format(reason=reason),
            reply_markup=subscribe_kb(),
            parse_mode="HTML",
        )
        return

    # Create DB record
    is_free = user.free_uses_left > 0
    transcription = await create_transcription(
        user_id=user.id,
        source_type=source_type,
        session=session,
        file_name=file_name,
        file_size_bytes=file_size,
        file_unique_id=file_unique_id,
        is_free=is_free,
    )

    if is_free:
        await decrement_free_uses(user.id, session)

    # Dispatch to Celery
    from src.worker.tasks.transcription import transcribe_task
    task = transcribe_task.delay(
        transcription_id=transcription.id,
        user_id=user.id,
        file_id=file_id,
        source_type=source_type,
    )

    await session.execute(
        __import__("sqlalchemy", fromlist=["update"]).update(
            __import__("src.db.models.transcription", fromlist=["Transcription"]).Transcription
        ).where(
            __import__("src.db.models.transcription", fromlist=["Transcription"]).Transcription.id == transcription.id
        ).values(celery_task_id=task.id)
    )
    await session.commit()

    await message.answer(
        PROCESSING.format(eta="1-3 мин", position=1),
        parse_mode="HTML",
    )


@router.message(F.voice)
async def handle_voice(message: Message, user: User, session: AsyncSession) -> None:
    v = message.voice
    await _handle_media(
        message, user, session,
        source_type="voice",
        file_id=v.file_id,
        file_unique_id=v.file_unique_id,
        file_size=v.file_size,
        mime_type="audio/ogg",
    )


@router.message(F.audio)
async def handle_audio(message: Message, user: User, session: AsyncSession) -> None:
    a = message.audio
    await _handle_media(
        message, user, session,
        source_type="audio",
        file_id=a.file_id,
        file_unique_id=a.file_unique_id,
        file_size=a.file_size,
        mime_type=a.mime_type,
        file_name=a.file_name,
    )


@router.message(F.video)
async def handle_video(message: Message, user: User, session: AsyncSession) -> None:
    v = message.video
    await _handle_media(
        message, user, session,
        source_type="video",
        file_id=v.file_id,
        file_unique_id=v.file_unique_id,
        file_size=v.file_size,
        mime_type=v.mime_type,
        file_name=v.file_name,
    )


@router.message(F.video_note)
async def handle_video_note(message: Message, user: User, session: AsyncSession) -> None:
    vn = message.video_note
    await _handle_media(
        message, user, session,
        source_type="video",
        file_id=vn.file_id,
        file_unique_id=vn.file_unique_id,
        file_size=vn.file_size,
        mime_type="video/mp4",
    )


@router.message(F.document)
async def handle_document(message: Message, user: User, session: AsyncSession) -> None:
    doc = message.document
    if not doc.mime_type or not validate_mime_type(doc.mime_type):
        await message.answer(UNSUPPORTED_FORMAT)
        return
    source_type = "audio" if doc.mime_type.startswith("audio/") else "video"
    await _handle_media(
        message, user, session,
        source_type=source_type,
        file_id=doc.file_id,
        file_unique_id=doc.file_unique_id,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
        file_name=doc.file_name,
    )
