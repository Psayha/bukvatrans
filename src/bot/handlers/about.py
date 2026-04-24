"""/about and /support — static informational screens."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.bot.texts.ru import ABOUT_TEXT, SUPPORT_TEXT
from src.config import settings
from src.db.models.user import User

router = Router()


@router.message(Command("about"))
async def cmd_about(message: Message) -> None:
    await message.answer(
        ABOUT_TEXT.format(
            company_name=settings.COMPANY_NAME,
            company_inn=settings.COMPANY_INN,
            company_ogrn=settings.COMPANY_OGRN,
            company_address=settings.COMPANY_ADDRESS,
            support_email=settings.SUPPORT_EMAIL,
        ),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


@router.message(Command("support"))
async def cmd_support(message: Message, user: User) -> None:
    handle = settings.SUPPORT_HANDLE.lstrip("@")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Написать в поддержку",
                    url=f"https://t.me/{handle}",
                )
            ]
        ]
    )
    await message.answer(
        SUPPORT_TEXT.format(support_handle=handle, user_id=user.id),
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
