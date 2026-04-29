import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import sentry_sdk
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger

from src.utils import metrics
from src.utils.logging import bind_job_context
from src.worker.app import app

logger = get_task_logger(__name__)


class TranscriptionTask(Task):
    abstract = True
    max_retries = 3

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error("transcription_task_failed task_id=%s exc=%s", task_id, exc)


def _run_async(coro):
    """Run a coroutine in a fresh event loop each task invocation.

    Celery workers are process-forked so `get_event_loop()` can return a loop
    that was closed in a parent; creating a fresh one is safer.
    """
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@app.task(
    bind=True,
    base=TranscriptionTask,
    name="src.worker.tasks.transcription.transcribe_task",
    queue="transcription",
)
def transcribe_task(
    self,
    transcription_id: str,
    user_id: int,
    source_type: str,
    file_id: Optional[str] = None,
    source_url: Optional[str] = None,
) -> dict:
    bind_job_context(
        transcription_id=transcription_id,
        user_id=user_id,
        source_type=source_type,
    )
    return _run_async(
        _transcribe_async(self, transcription_id, user_id, source_type, file_id, source_url)
    )


async def _download_from_s3(s3_key: str, output_dir: Path) -> Path:
    """Download a file from S3 directly, bypassing URL validation.

    Used for web uploads where the API already staged the file.
    """
    import asyncio
    import boto3
    from botocore.client import Config
    from src.config import settings

    suffix = Path(s3_key).suffix or ".mp3"
    out_path = output_dir / f"{uuid.uuid4()}{suffix}"

    def _dl():
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            config=Config(signature_version="s3v4"),
        )
        client.download_file(settings.S3_BUCKET, s3_key, str(out_path))

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _dl)
    return out_path


async def _get_user_language(user_id: int) -> str:
    """Fetch language preference from Redis; fall back to Russian."""
    import redis.asyncio as aioredis
    from src.config import settings
    try:
        r = aioredis.from_url(settings.redis_cache_url, decode_responses=True)
        lang = await r.get(f"lang:{user_id}")
        await r.close()
        if lang and lang.strip():
            return lang.strip()
    except Exception:
        pass
    return "ru"


async def _transcribe_async(
    task,
    transcription_id: str,
    user_id: int,
    source_type: str,
    file_id: Optional[str],
    source_url: Optional[str],
) -> dict:
    import time as _time
    _started = _time.perf_counter()
    sentry_sdk.set_tag("transcription_id", transcription_id)
    sentry_sdk.set_tag("source_type", source_type)
    sentry_sdk.set_context("job", {"user_id": user_id, "source_type": source_type})

    from src.db.base import async_session_factory
    from src.db.repositories.transcription import update_transcription_status, get_transcription
    from src.db.repositories.user import get_user, deduct_balance
    from src.services.transcription import transcribe_audio
    from src.services.audio_processor import get_audio_duration, extract_audio
    from src.services.billing import calculate_charge
    from src.services.notification import send_message, send_document
    from src.utils.formatters import format_duration, format_balance
    from src.bot.texts.ru import TRANSCRIPTION_DONE, ERROR_DOWNLOAD

    async with async_session_factory() as session:
        await update_transcription_status(transcription_id, "processing", session)
        transcription = await get_transcription(transcription_id, session)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        audio_path: Optional[Path] = None

        try:
            # Download file
            if file_id:
                audio_path = await _download_telegram_file(file_id, tmp_path, source_type)
            elif source_url and source_url.startswith("s3://"):
                # Web upload: file was already uploaded to S3 by the API.
                s3_key = source_url[len("s3://"):]
                audio_path = await _download_from_s3(s3_key, tmp_path)
            elif source_url:
                from src.services.downloader import download_url, UnsafeURLError, URLTooLargeError
                try:
                    audio_path = await download_url(source_url, tmp_path)
                except (UnsafeURLError, URLTooLargeError) as e:
                    logger.warning("url_rejected user_id=%s err=%s", user_id, e)
                    await send_message(user_id, str(e) if isinstance(e, URLTooLargeError) else ERROR_DOWNLOAD)
                    async with async_session_factory() as session:
                        await update_transcription_status(
                            transcription_id, "failed", session,
                            error_message=str(e),
                        )
                    return {"status": "failed", "error": str(e)}
                except Exception as e:
                    logger.error("download_failed user_id=%s err=%s", user_id, e)
                    await send_message(user_id, ERROR_DOWNLOAD)
                    async with async_session_factory() as session:
                        await update_transcription_status(
                            transcription_id, "failed", session,
                            error_message=str(e),
                        )
                    return {"status": "failed", "error": str(e)}

            if not audio_path or not audio_path.exists():
                raise FileNotFoundError("Audio file not found after download")

            # Extract audio if video
            if source_type in ("video",) and audio_path.suffix.lower() not in (".mp3", ".wav", ".ogg"):
                extracted = tmp_path / f"{uuid.uuid4()}.mp3"
                audio_path = await extract_audio(audio_path, extracted)

            duration = await get_audio_duration(audio_path)

            lang = await _get_user_language(user_id)

            text, segments = await transcribe_audio(audio_path, language=lang)

            # Charge balance
            seconds_charged = 0
            async with async_session_factory() as session:
                user = await get_user(user_id, session)
                if not user.has_active_unlimited_subscription():
                    if transcription and transcription.is_free:
                        seconds_charged = 0
                    else:
                        seconds_charged = calculate_charge(int(duration))
                        await deduct_balance(user_id, seconds_charged, session)
                user = await get_user(user_id, session)
                balance = user.balance_seconds

            # Save result (include detected language, segments optional)
            async with async_session_factory() as session:
                t = await get_transcription(transcription_id, session)
                if t:
                    t.language = lang
                    await session.commit()
                await update_transcription_status(
                    transcription_id, "done", session,
                    result_text=text,
                    duration_seconds=int(duration),
                    seconds_charged=seconds_charged,
                )

            # Send result to user
            done_text = TRANSCRIPTION_DONE.format(
                duration=format_duration(int(duration)),
                charged=format_duration(seconds_charged) if seconds_charged else "0 (бесплатно)",
                balance=format_balance(balance),
            )
            buttons = [
                [
                    {"text": "📋 Конспект", "callback_data": f"summary:{transcription_id}"},
                    {"text": "📄 DOCX", "callback_data": f"docx:{transcription_id}"},
                ]
            ]
            if source_type in ("video", "youtube", "rutube", "vk", "ok"):
                buttons.append(
                    [{"text": "📑 SRT субтитры", "callback_data": f"srt:{transcription_id}"}]
                )
            await send_message(
                user_id,
                done_text,
                parse_mode="HTML",
                reply_markup={"inline_keyboard": buttons},
            )

            if len(text) <= 4096:
                await send_message(user_id, text)
            else:
                txt_bytes = text.encode("utf-8")
                await send_document(user_id, txt_bytes, "transcription.txt")

            metrics.transcriptions_total.labels(status="done", source_type=source_type).inc()
            metrics.transcription_duration_seconds.labels(source_type=source_type).observe(
                _time.perf_counter() - _started
            )
            return {"status": "done", "duration": int(duration)}

        except SoftTimeLimitExceeded as e:
            logger.error("transcription_soft_timeout user_id=%s", user_id)
            metrics.transcriptions_total.labels(status="timeout", source_type=source_type).inc()
            await _refund_and_notify(transcription_id, user_id, str(e))
            return {"status": "failed", "error": "timeout"}
        except Exception as e:
            logger.error("transcription_error user_id=%s err=%s", user_id, e, exc_info=True)
            metrics.transcriptions_total.labels(status="failed", source_type=source_type).inc()
            await _refund_and_notify(transcription_id, user_id, str(e))
            return {"status": "failed", "error": str(e)}


async def _refund_and_notify(transcription_id: str, user_id: int, error_message: str) -> None:
    """Refund charged seconds AND mark transcription failed in one transaction.

    Doing both in a single `session.begin()` block prevents the split-brain
    state where the balance was credited but the job is still "processing"
    (which would let the user re-trigger the same refund via /cancel).
    """
    from datetime import datetime

    from src.bot.texts.ru import ERROR_TRANSCRIPTION
    from src.db.base import async_session_factory
    from src.db.models.transcription import Transcription
    from src.db.models.user import User
    from src.services.notification import send_message

    try:
        async with async_session_factory() as session:
            async with session.begin():
                t = await session.get(Transcription, transcription_id)
                if t is None:
                    return
                # Idempotency: if the user (or a previous retry) already
                # moved the job out of pending/processing, don't double-refund.
                if t.status not in ("pending", "processing"):
                    return
                if (t.seconds_charged or 0) > 0:
                    try:
                        user = await session.get(User, user_id, with_for_update=True)
                    except Exception:
                        user = await session.get(User, user_id)
                    if user is not None:
                        user.balance_seconds = (user.balance_seconds or 0) + t.seconds_charged
                t.status = "failed"
                t.error_message = error_message[:1000]
                t.completed_at = datetime.utcnow()
    except Exception:
        logger.error("refund_failed user_id=%s", user_id, exc_info=True)

    try:
        await send_message(user_id, ERROR_TRANSCRIPTION)
    except Exception:
        logger.warning("notify_failed user_id=%s", user_id, exc_info=True)


async def _download_telegram_file(file_id: str, output_dir: Path, source_type: str) -> Path:
    import httpx
    from src.config import settings

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.get(
            f"https://api.telegram.org/bot{settings.BOT_TOKEN}/getFile",
            params={"file_id": file_id},
        )
        r.raise_for_status()
        file_path = r.json()["result"]["file_path"]
        ext = Path(file_path).suffix or ".ogg"

        url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file_path}"
        out_path = output_dir / f"{uuid.uuid4()}{ext}"
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(out_path, "wb") as f:
                async for chunk in response.aiter_bytes(8192):
                    f.write(chunk)
        return out_path
