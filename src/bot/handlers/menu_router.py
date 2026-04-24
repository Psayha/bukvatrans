"""Reply-keyboard button handlers.

The persistent reply keyboard sends its button label as a plain text
message. We match on the exact label and dispatch to the corresponding
command flow. Keeps command handlers reusable both from typing the
command and from tapping the button.
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.handlers.about import cmd_support
from src.bot.texts.ru import (
    BTN_NEW,
    BTN_PLANS,
    BTN_REFERRAL,
    BTN_SETTINGS,
    BTN_SUPPORT,
    NEW_TRANSCRIPTION_PROMPT,
)
from src.db.models.user import User

router = Router()


@router.message(F.text == BTN_NEW)
async def on_btn_new(message: Message) -> None:
    await message.answer(NEW_TRANSCRIPTION_PROMPT, parse_mode="HTML")


@router.message(F.text == BTN_PLANS)
async def on_btn_plans(message: Message) -> None:
    # Forward to the existing /subscription handler by calling it directly.
    from src.bot.handlers.payment import cmd_subscribe
    await cmd_subscribe(message)


@router.message(F.text == BTN_REFERRAL)
async def on_btn_referral(
    message: Message, user: User, session: AsyncSession
) -> None:
    from src.bot.handlers.referral import cmd_referral
    await cmd_referral(message, user, session)


@router.message(F.text == BTN_SETTINGS)
async def on_btn_settings(
    message: Message, user: User, session: AsyncSession, state: FSMContext
) -> None:
    # Settings handler is added in Block 3; once it exists, swap this to
    # call it. For now surface a brief placeholder so the button is live.
    try:
        from src.bot.handlers.user_settings import cmd_settings
    except ImportError:
        await message.answer("⚙️ Настройки временно недоступны.")
        return
    await cmd_settings(message, user, session, state)


@router.message(F.text == BTN_SUPPORT)
async def on_btn_support(message: Message, user: User) -> None:
    await cmd_support(message, user)
