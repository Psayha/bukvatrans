import redis.asyncio as aioredis
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.texts.ru import (
    LANGUAGE_SET,
    SUMMARY_ERROR,
    SUMMARY_GENERATING,
    SUMMARY_READY,
)
from src.config import settings
from src.db.models.user import User
from src.db.repositories.transcription import get_transcription

router = Router()


@router.callback_query(F.data.startswith("summary:"))
async def cb_summary(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    transcription_id = callback.data.split(":", 1)[1]
    transcription = await get_transcription(transcription_id, session)

    if not transcription or transcription.user_id != user.id:
        await callback.answer("Транскрибация не найдена.", show_alert=True)
        return

    if transcription.summary_text:
        await callback.message.answer(
            SUMMARY_READY.format(summary=transcription.summary_text),
            parse_mode="HTML",
        )
        await callback.answer()
        return

    await callback.message.answer(SUMMARY_GENERATING)
    await callback.answer()

    from src.worker.tasks.summary import summary_task
    summary_task.delay(transcription_id=transcription_id, user_id=user.id)


@router.callback_query(F.data.startswith("docx:"))
async def cb_docx(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    transcription_id = callback.data.split(":", 1)[1]
    transcription = await get_transcription(transcription_id, session)

    if not transcription or transcription.user_id != user.id or not transcription.result_text:
        await callback.answer("Текст не найден.", show_alert=True)
        return

    await callback.answer("Генерирую DOCX...")
    from src.worker.tasks.summary import docx_task
    docx_task.delay(transcription_id=transcription_id, user_id=user.id)


@router.callback_query(F.data.startswith("srt:"))
async def cb_srt(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    transcription_id = callback.data.split(":", 1)[1]
    transcription = await get_transcription(transcription_id, session)

    if not transcription or transcription.user_id != user.id or not transcription.result_text:
        await callback.answer("Субтитры недоступны.", show_alert=True)
        return

    await callback.answer("Генерирую SRT...")
    from src.worker.tasks.summary import srt_task
    srt_task.delay(transcription_id=transcription_id, user_id=user.id)


@router.callback_query(F.data.startswith("lang:"))
async def cb_language(callback: CallbackQuery, user: User) -> None:
    lang = callback.data.split(":", 1)[1]
    # Minimal allow-list to avoid arbitrary Redis keys from untrusted callback data.
    if lang not in {"ru", "en", "uk", "de", "fr", "es", "it", "pl", "auto"}:
        await callback.answer("Неизвестный язык.", show_alert=True)
        return
    redis = aioredis.from_url(settings.redis_cache_url, decode_responses=True)
    try:
        await redis.set(f"lang:{user.id}", lang, ex=86400 * 30)
    finally:
        await redis.close()
    await callback.message.edit_text(LANGUAGE_SET.format(language=lang), parse_mode="HTML")
    await callback.answer()
