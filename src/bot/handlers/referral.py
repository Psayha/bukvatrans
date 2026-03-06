from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.db.models.user import User
from src.bot.texts.ru import REFERRAL_TEXT

router = Router()


@router.message(Command("referral"))
async def cmd_referral(message: Message, user: User) -> None:
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user.id}"

    text = REFERRAL_TEXT.format(
        ref_link=ref_link,
        referrals_count=0,
        bonus_earned=0,
    )
    await message.answer(text, parse_mode="HTML")
