from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.texts.ru import REFERRAL_TEXT
from src.db.models.transaction import Transaction
from src.db.models.user import User
from src.services.billing import REFERRAL_FREE_MONTH_THRESHOLD
from src.utils.gamification import progress_bar

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

    # "paid_count" = unique referred users who made at least one successful
    # real payment. Capped at the milestone threshold for the progress bar.
    paid_count = await session.scalar(
        select(func.count(distinct(Transaction.user_id))).where(
            Transaction.user_id.in_(
                select(User.id).where(User.referrer_id == user.id)
            ),
            Transaction.status == "success",
            Transaction.type.in_(["subscription", "topup"]),
        )
    ) or 0

    ratio = min(1.0, paid_count / REFERRAL_FREE_MONTH_THRESHOLD)
    bar = progress_bar(ratio, width=REFERRAL_FREE_MONTH_THRESHOLD)

    text = REFERRAL_TEXT.format(
        ref_link=ref_link,
        referrals_count=referrals_count,
        paid_count=paid_count,
        threshold=REFERRAL_FREE_MONTH_THRESHOLD,
        progress_bar=bar,
        bonus_earned=f"{float(bonus_earned):.2f}",
    )

    share_url = (
        f"https://t.me/share/url?url={ref_link}"
        "&text=%D0%94%D0%B5%D0%BB%D0%B0%D1%8E%20%D1%80%D0%B0%D1%81%D1%88%D0%B8%D1%84%D1%80%D0%BE%D0%B2%D0%BA%D1%83%20%D0%B0%D1%83%D0%B4%D0%B8%D0%BE%20%D1%87%D0%B5%D1%80%D0%B5%D0%B7%20%D0%91%D1%83%D0%BA%D0%B2%D0%B8%D1%86%D1%83"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться", url=share_url)],
    ])
    await message.answer(
        text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True
    )
