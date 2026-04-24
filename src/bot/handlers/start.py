"""Onboarding: /start + 152-ФЗ consent gate + two-stage welcome.

Flow for a brand-new user:
  /start → consent prompt (inline ✅ button) → click → welcome part 1
         → welcome part 2 (with Meta disclaimer) → main reply keyboard.

Flow for a returning user who already consented:
  /start → short "welcome back" + balance + sub status + reply keyboard.
"""
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.keyboards.reply import main_menu_kb
from src.bot.texts.ru import (
    CONSENT_ACCEPTED,
    CONSENT_BUTTON,
    CONSENT_PROMPT,
    HELP_TEXT,
    MENU_PROMPT,
    NO_SUBSCRIPTION,
    WELCOME_EXISTING,
    WELCOME_PART_1,
    WELCOME_PART_2,
)
from src.db.models.transcription import Transcription
from src.db.models.user import User
from src.services.billing import PLANS
from src.utils.formatters import format_balance

router = Router()


@router.message(CommandStart())
async def cmd_start(
    message: Message, user: User, session: AsyncSession
) -> None:
    if user.consent_at is None:
        await _ask_for_consent(message)
        return
    await _welcome_back(message, user)


async def _ask_for_consent(message: Message) -> None:
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=CONSENT_BUTTON, callback_data="consent:accept")],
    ])
    await message.answer(CONSENT_PROMPT, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "consent:accept")
async def on_consent(
    callback: CallbackQuery, user: User, session: AsyncSession
) -> None:
    if user.consent_at is None:
        user.consent_at = datetime.utcnow()
        await session.commit()

    try:
        await callback.message.edit_text(CONSENT_ACCEPTED)
    except Exception:
        pass

    await _send_two_stage_welcome(callback.message, session)
    await callback.answer()


async def _welcome_back(message: Message, user: User) -> None:
    subscription_line = NO_SUBSCRIPTION
    if user.has_active_subscription():
        for sub in user.subscriptions:
            if sub.status == "active" and sub.expires_at > datetime.utcnow():
                plan_label = PLANS.get(sub.plan, {}).get("label", sub.plan)
                subscription_line = f"{plan_label} до {sub.expires_at:%d.%m.%Y}"
                break

    await message.answer(
        WELCOME_EXISTING.format(
            name=user.get_display_name(),
            balance=format_balance(user.balance_seconds),
            free_uses=user.free_uses_left,
            subscription=subscription_line,
        ),
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


async def _send_two_stage_welcome(message: Message, session: AsyncSession) -> None:
    stats = await _bot_stats(session)
    await message.answer(
        WELCOME_PART_1.format(**stats),
        parse_mode="HTML",
    )
    await message.answer(
        WELCOME_PART_2.format(audio_language="🌍 Авто (определится автоматически)"),
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


async def _bot_stats(session: AsyncSession) -> dict[str, int]:
    """Numbers for the welcome social proof. Real numbers, not vanity.

    On day-1 of deployment these are all ~0; as traffic grows the welcome
    message grows with it.
    """
    users_total = await session.scalar(select(func.count(User.id))) or 0
    transcriptions_total = await session.scalar(
        select(func.count(Transcription.id)).where(Transcription.status == "done")
    ) or 0
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    transcriptions_today = await session.scalar(
        select(func.count(Transcription.id)).where(
            Transcription.status == "done",
            Transcription.created_at >= today_start,
        )
    ) or 0
    return {
        "users_total": users_total,
        "transcriptions_total": transcriptions_total,
        "transcriptions_today": transcriptions_today,
    }


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")


@router.message(Command("menu"))
async def cmd_menu(message: Message) -> None:
    """Re-send the main reply keyboard. Useful if a user hid it."""
    await message.answer(
        MENU_PROMPT,
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
