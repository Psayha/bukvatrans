from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.texts.ru import REFERRAL_TEXT
from src.db.models.transaction import Transaction
from src.db.models.user import User

router = Router()


@router.message(Command("referral"))
async def cmd_referral(message: Message, user: User, session: AsyncSession) -> None:
    bot_info = await message.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user.id}"

    referrals_count = await session.scalar(
        select(func.count(User.id)).where(User.referrer_id == user.id)
    ) or 0

    bonus_earned = await session.scalar(
        select(func.coalesce(func.sum(Transaction.amount_rub), 0)).where(
            Transaction.user_id == user.id,
            Transaction.type == "referral_bonus",
            Transaction.status == "success",
        )
    ) or 0

    text = REFERRAL_TEXT.format(
        ref_link=ref_link,
        referrals_count=referrals_count,
        bonus_earned=f"{float(bonus_earned):.2f}",
    )
    await message.answer(text, parse_mode="HTML")
