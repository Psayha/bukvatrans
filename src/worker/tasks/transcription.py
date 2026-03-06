import asyncio
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from celery import Task
from celery.utils.log import get_task_logger

from src.worker.app import app

logger = get_task_logger(__name__)


class TranscriptionTask(Task):
    abstract = True
    max_retries = 3

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"Task {task_id} failed: {exc}")


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
    return asyncio.get_event_loop().run_until_complete(
        _transcribe_async(self, transcription_id, user_id, source_type, file_id, source_url)
    )


async def _transcribe_async(
    task,
    transcription_id: str,
    user_id: int,
    source_type: str,
    file_id: Optional[str],
    source_url: Optional[str],
) -> dict:
    from src.db.base import async_session_factory
    from src.db.repositories.transcription import update_transcription_status, get_transcription
    from src.db.repositories.user import get_user, deduct_balance, decrement_free_uses
    from src.services.transcription import transcribe_audio
    from src.services.audio_processor import get_audio_duration, extract_audio
    from src.services.billing import calculate_charge
    from src.services.notification import send_message, send_document
    from src.bot.keyboards.inline import transcription_result_kb
    from src.utils.formatters import format_duration, format_balance
    from src.bot.texts.ru import TRANSCRIPTION_DONE, ERROR_TRANSCRIPTION, ERROR_DOWNLOAD
    from src.config import settings
    import httpx

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
            elif source_url:
                from src.services.downloader import download_url
                try:
                    audio_path = await download_url(source_url, tmp_path)
                except Exception as e:
                    logger.error(f"Download failed: {e}")
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

            # Get duration
            duration = await get_audio_duration(audio_path)

            # Transcribe
            async with async_session_factory() as session:
                user = await get_user(user_id, session)
                lang = "ru"  # TODO: fetch from Redis user preference

            text, _ = await transcribe_audio(audio_path, language=lang)

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

            # Save result
            async with async_session_factory() as session:
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
            await send_message(
                user_id,
                done_text,
                parse_mode="HTML",
                reply_markup={
                    "inline_keyboard": [
                        [
                            {"text": "📋 Конспект", "callback_data": f"summary:{transcription_id}"},
                            {"text": "📄 DOCX", "callback_data": f"docx:{transcription_id}"},
                        ]
                    ]
                },
            )

            # Also send as file if text > 4096 chars
            if len(text) <= 4096:
                await send_message(user_id, text)
            else:
                txt_bytes = text.encode("utf-8")
                await send_document(user_id, txt_bytes, "transcription.txt")

            return {"status": "done", "duration": int(duration)}

        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            async with async_session_factory() as session:
                # Refund
                t = await get_transcription(transcription_id, session)
                if t and t.seconds_charged > 0:
                    await add_balance_import(user_id, t.seconds_charged, session)
                await update_transcription_status(
                    transcription_id, "failed", session,
                    error_message=str(e),
                )
            await send_message(user_id, ERROR_TRANSCRIPTION)
            return {"status": "failed", "error": str(e)}


async def _download_telegram_file(file_id: str, output_dir: Path, source_type: str) -> Path:
    import httpx
    from src.config import settings

    async with httpx.AsyncClient(timeout=300) as client:
        # Get file info
        r = await client.get(
            f"https://api.telegram.org/bot{settings.BOT_TOKEN}/getFile",
            params={"file_id": file_id},
        )
        r.raise_for_status()
        file_path = r.json()["result"]["file_path"]
        ext = Path(file_path).suffix or ".ogg"

        # Download
        url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file_path}"
        out_path = output_dir / f"{uuid.uuid4()}{ext}"
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(out_path, "wb") as f:
                async for chunk in response.aiter_bytes(8192):
                    f.write(chunk)
        return out_path


async def add_balance_import(user_id, seconds, session):
    from src.db.repositories.user import add_balance
    await add_balance(user_id, seconds, session)
