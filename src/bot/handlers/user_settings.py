"""User-facing /settings panel — language, AI model, format, notifications.

This is the only place ordinary users can change runtime settings. Admin
mirrors exist (/admin_model), but from the user side everything flows
through /settings → submenu → pick → confirm.

Persistence: each setting has its own Redis key in the cache DB so we
don't need new columns for flags that rarely change. Missing keys mean
"default".
"""
import redis.asyncio as aioredis
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.inline import language_kb
from src.bot.keyboards.reply import main_menu_kb
from src.bot.texts.ru import (
    FORMAT_PROMPT,
    FORMAT_SET,
    LANGUAGE_PROMPT,
    MODEL_PICK_PROMPT,
    MODEL_SET,
    NOTIFICATIONS_OFF,
    NOTIFICATIONS_ON,
    SETTINGS_BTN_BACK,
    SETTINGS_BTN_FORMAT,
    SETTINGS_BTN_LANG_AUDIO,
    SETTINGS_BTN_MODEL,
    SETTINGS_BTN_NOTIFY,
    SETTINGS_TITLE,
)
from src.config import settings
from src.db.models.transcription import Transcription
from src.db.models.user import User
from src.utils import admin_model
from src.utils.gamification import saved_time_phrase

router = Router()


# ---------- main settings entry ----------

def _settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=SETTINGS_BTN_LANG_AUDIO, callback_data="settings:lang")],
        [InlineKeyboardButton(text=SETTINGS_BTN_MODEL, callback_data="settings:model")],
        [InlineKeyboardButton(text=SETTINGS_BTN_FORMAT, callback_data="settings:format")],
        [InlineKeyboardButton(text=SETTINGS_BTN_NOTIFY, callback_data="settings:notify")],
        [InlineKeyboardButton(text=SETTINGS_BTN_BACK, callback_data="settings:exit")],
    ])


@router.message(Command("settings"))
async def cmd_settings(
    message: Message, user: User, session: AsyncSession, state: FSMContext
) -> None:
    await state.clear()
    total_transcriptions = await session.scalar(
        select(func.count(Transcription.id)).where(Transcription.user_id == user.id)
    ) or 0
    total_audio = await session.scalar(
        select(func.coalesce(func.sum(Transcription.duration_seconds), 0)).where(
            Transcription.user_id == user.id,
            Transcription.status == "done",
        )
    ) or 0

    text = SETTINGS_TITLE.format(
        user_id=user.id,
        total_transcriptions=total_transcriptions,
        saved_time=saved_time_phrase(total_audio),
        ai_dialogs=user.ai_dialogs_count,
    )
    await message.answer(text, reply_markup=_settings_kb(), parse_mode="HTML")


@router.callback_query(F.data == "settings:menu")
async def cb_settings_back(
    callback: CallbackQuery, user: User, session: AsyncSession
) -> None:
    total_transcriptions = await session.scalar(
        select(func.count(Transcription.id)).where(Transcription.user_id == user.id)
    ) or 0
    total_audio = await session.scalar(
        select(func.coalesce(func.sum(Transcription.duration_seconds), 0)).where(
            Transcription.user_id == user.id,
            Transcription.status == "done",
        )
    ) or 0
    text = SETTINGS_TITLE.format(
        user_id=user.id,
        total_transcriptions=total_transcriptions,
        saved_time=saved_time_phrase(total_audio),
        ai_dialogs=user.ai_dialogs_count,
    )
    try:
        await callback.message.edit_text(text, reply_markup=_settings_kb(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=_settings_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "settings:exit")
async def cb_settings_exit(callback: CallbackQuery) -> None:
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("🏠", reply_markup=main_menu_kb())
    await callback.answer()


# ---------- audio language ----------

@router.callback_query(F.data == "settings:lang")
async def cb_settings_lang(callback: CallbackQuery) -> None:
    try:
        await callback.message.edit_text(
            LANGUAGE_PROMPT, reply_markup=language_kb(0), parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            LANGUAGE_PROMPT, reply_markup=language_kb(0), parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("langpage:"))
async def cb_langpage(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":", 1)[1])
    try:
        await callback.message.edit_reply_markup(reply_markup=language_kb(page))
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ---------- model picker (user-facing, curated subset) ----------

# A short, sane list shown directly — no API round-trip, so even with
# OpenRouter down users can still see the panel. Keep these IDs in sync
# with popular slugs from openrouter.ai/models.
_USER_MODEL_OPTIONS = [
    ("anthropic/claude-3.5-haiku", "Claude 3.5 Haiku — быстрый"),
    ("openai/gpt-4o-mini", "GPT-4o mini — дешёвый"),
    ("google/gemini-2.5-flash", "Gemini 2.5 Flash"),
    ("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B"),
    ("deepseek/deepseek-chat", "DeepSeek Chat"),
]


@router.callback_query(F.data == "settings:model")
async def cb_settings_model(callback: CallbackQuery) -> None:
    active = await admin_model.get_active_model()
    rows = [
        [InlineKeyboardButton(
            text=("⭐️ " if mid == active else "") + label,
            callback_data=f"setmodel:{mid}",
        )]
        for mid, label in _USER_MODEL_OPTIONS
    ]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings:menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await callback.message.edit_text(
            MODEL_PICK_PROMPT.format(active=active),
            reply_markup=kb, parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            MODEL_PICK_PROMPT.format(active=active),
            reply_markup=kb, parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("setmodel:"))
async def cb_setmodel(callback: CallbackQuery) -> None:
    model = callback.data.split(":", 1)[1]
    if model not in {m for m, _ in _USER_MODEL_OPTIONS}:
        await callback.answer("Неизвестная модель.", show_alert=True)
        return
    await admin_model.set_active_model(model)
    await callback.answer("Готово ✓")
    try:
        await callback.message.edit_text(
            MODEL_SET.format(model=model), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="◀️ Назад", callback_data="settings:menu")
            ]]),
        )
    except Exception:
        pass


# ---------- transcription format ----------

_FORMAT_OPTIONS = [
    ("txt", "📄 Текстом или файлом (по умолчанию)"),
    ("docx", "📄 DOCX-файл"),
    ("srt", "📑 SRT субтитры"),
]


@router.callback_query(F.data == "settings:format")
async def cb_settings_format(
    callback: CallbackQuery, user: User
) -> None:
    active = await _get_format(user.id)
    rows = [
        [InlineKeyboardButton(
            text=("⭐️ " if k == active else "") + label,
            callback_data=f"setfmt:{k}",
        )]
        for k, label in _FORMAT_OPTIONS
    ]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings:menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    try:
        await callback.message.edit_text(
            FORMAT_PROMPT, reply_markup=kb, parse_mode="HTML",
        )
    except Exception:
        await callback.message.answer(
            FORMAT_PROMPT, reply_markup=kb, parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("setfmt:"))
async def cb_setfmt(callback: CallbackQuery, user: User) -> None:
    fmt = callback.data.split(":", 1)[1]
    if fmt not in {k for k, _ in _FORMAT_OPTIONS}:
        await callback.answer("Неизвестный формат.", show_alert=True)
        return
    await _set_format(user.id, fmt)
    await callback.answer("Готово ✓")
    label = next((lbl for k, lbl in _FORMAT_OPTIONS if k == fmt), fmt)
    try:
        await callback.message.edit_text(
            FORMAT_SET.format(fmt=label), parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="◀️ Назад", callback_data="settings:menu")
            ]]),
        )
    except Exception:
        pass


# ---------- notifications toggle ----------

@router.callback_query(F.data == "settings:notify")
async def cb_settings_notify(callback: CallbackQuery, user: User) -> None:
    enabled = await _get_notifications(user.id)
    new_state = not enabled
    await _set_notifications(user.id, new_state)
    text = NOTIFICATIONS_ON if new_state else NOTIFICATIONS_OFF
    await callback.answer(text, show_alert=True)


# ---------- tiny Redis helpers ----------

def _redis() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_cache_url, decode_responses=True)


async def _get_format(user_id: int) -> str:
    try:
        r = _redis()
        try:
            v = await r.get(f"fmt:{user_id}")
        finally:
            await r.close()
        return v or "txt"
    except Exception:
        return "txt"


async def _set_format(user_id: int, fmt: str) -> None:
    try:
        r = _redis()
        try:
            await r.set(f"fmt:{user_id}", fmt)
        finally:
            await r.close()
    except Exception:
        pass


async def _get_notifications(user_id: int) -> bool:
    try:
        r = _redis()
        try:
            v = await r.get(f"notify:{user_id}")
        finally:
            await r.close()
        # Default ON.
        return v != "0"
    except Exception:
        return True


async def _set_notifications(user_id: int, enabled: bool) -> None:
    try:
        r = _redis()
        try:
            await r.set(f"notify:{user_id}", "1" if enabled else "0")
        finally:
            await r.close()
    except Exception:
        pass
