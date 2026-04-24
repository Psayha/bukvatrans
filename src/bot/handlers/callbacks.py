import redis.asyncio as aioredis
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.texts.ru import (
    AI_CHAT_MOCK_ANSWER,
    AI_CHAT_PROMPT,
    LANGUAGE_SET,
    SUMMARY_DISABLED,
    SUMMARY_READY,
)
from src.config import settings
from src.db.models.user import User
from src.db.repositories.transcription import get_transcription

router = Router()


class AiChatFlow(StatesGroup):
    """Tiny dialog FSM for the "Спросить ИИ" button.

    For the demo build the answer is canned (OpenRouter is wired in
    the service layer but not exposed here yet). The state still tracks
    transcription_id so the prompt can quote it.
    """
    asking = State()


# ---------- Summary (disabled for demo) ----------

@router.callback_query(F.data.startswith("summary:"))
async def cb_summary(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    transcription_id = callback.data.split(":", 1)[1]
    transcription = await get_transcription(transcription_id, session)
    if not transcription or transcription.user_id != user.id:
        await callback.answer("Транскрибация не найдена.", show_alert=True)
        return
    # If a summary was somehow produced already (e.g. older run), still show it.
    if transcription.summary_text:
        await callback.message.answer(
            SUMMARY_READY.format(summary=transcription.summary_text),
            parse_mode="HTML",
        )
        await callback.answer()
        return
    # Demo build: feature off. Real path is summary_task.delay(...).
    await callback.message.answer(SUMMARY_DISABLED, parse_mode="HTML")
    await callback.answer()


# ---------- DOCX ----------

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


# ---------- SRT ----------

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


# ---------- AI chat mock ----------

@router.callback_query(F.data.startswith("ai_chat:"))
async def cb_ai_chat(
    callback: CallbackQuery,
    user: User,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    transcription_id = callback.data.split(":", 1)[1]
    transcription = await get_transcription(transcription_id, session)
    if not transcription or transcription.user_id != user.id:
        await callback.answer("Транскрибация не найдена.", show_alert=True)
        return

    await state.set_state(AiChatFlow.asking)
    await state.update_data(transcription_id=transcription_id)
    await callback.message.answer(AI_CHAT_PROMPT, parse_mode="HTML")
    await callback.answer()


@router.message(AiChatFlow.asking)
async def on_ai_question(
    message: Message, user: User, session: AsyncSession, state: FSMContext
) -> None:
    """Bump the dialog counter and return the demo answer.

    Real wiring goes through services.summary / OpenRouter; we stub it
    deliberately so the demo build doesn't depend on OpenRouter being
    reachable. State is kept so follow-ups still land here.
    """
    user.ai_dialogs_count = (user.ai_dialogs_count or 0) + 1
    await session.commit()
    await message.answer(AI_CHAT_MOCK_ANSWER, parse_mode="HTML")


# ---------- Audio language picker ----------

@router.callback_query(F.data.startswith("lang:"))
async def cb_language(callback: CallbackQuery, user: User) -> None:
    lang = callback.data.split(":", 1)[1]
    # Allow-list keeps untrusted callback data out of Redis key space.
    _ALLOWED = {
        "auto", "ru", "en", "uk", "kk", "de", "fr", "es", "it",
        "pt", "zh", "ja", "hi", "tr", "nl", "pl",
    }
    if lang not in _ALLOWED:
        await callback.answer("Неизвестный язык.", show_alert=True)
        return
    redis = aioredis.from_url(settings.redis_cache_url, decode_responses=True)
    try:
        await redis.set(f"lang:{user.id}", lang, ex=86400 * 365)
    finally:
        await redis.close()
    try:
        await callback.message.edit_text(
            LANGUAGE_SET.format(language=lang), parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            LANGUAGE_SET.format(language=lang), parse_mode="HTML"
        )
    await callback.answer("Готово ✓")
