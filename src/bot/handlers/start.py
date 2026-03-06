from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User
from src.bot.texts.ru import START_NEW_USER, START_EXISTING_USER, HELP_TEXT
from src.bot.keyboards.inline import subscribe_kb
from src.utils.formatters import format_balance

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, is_new_user: bool) -> None:
    if is_new_user:
        text = START_NEW_USER.format(name=user.get_display_name())
    else:
        text = START_EXISTING_USER.format(
            name=user.get_display_name(),
            balance=format_balance(user.balance_seconds),
            free_uses=user.free_uses_left,
        )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")
