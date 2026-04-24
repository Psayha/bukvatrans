"""Create free-seconds promo codes from the bot. No 2FA — promo codes
don't hand out money directly, they still expire/limit, and not every
admin task deserves a second-admin round-trip."""
from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.handlers.admin._common import guard
from src.db.models.promo_code import PromoCode
from src.db.models.user import User
from src.utils.logging import get_logger

router = Router()
logger = get_logger(__name__)

_USAGE = (
    "Использование:\n"
    "<code>/admin_promo CREATE CODE SECONDS [MAX_USES] [DAYS_TTL]</code>\n\n"
    "Пример:\n"
    "<code>/admin_promo CREATE WELCOME30 1800 100 14</code>\n"
    "— 30 мин бесплатно, 100 активаций, истекает через 14 дней."
)


@router.message(Command("admin_promo"))
async def cmd_admin_promo(
    message: Message, user: User, session: AsyncSession
) -> None:
    if not await guard(user):
        return

    parts = (message.text or "").split()
    if len(parts) < 4 or parts[1].upper() != "CREATE":
        await message.answer(_USAGE, parse_mode="HTML")
        return

    code = parts[2].upper()
    try:
        seconds = int(parts[3])
        max_uses = int(parts[4]) if len(parts) > 4 else None
        days_ttl = int(parts[5]) if len(parts) > 5 else None
    except ValueError:
        await message.answer("Неверные числовые аргументы.")
        return

    if not (1 <= len(code) <= 50) or not code.replace("_", "").isalnum():
        await message.answer("Код должен быть 1..50 символов, только буквы/цифры/подчёркивание.")
        return
    if seconds <= 0 or seconds > 10 * 3600:
        await message.answer("SECONDS: от 1 до 36000 (10 часов).")
        return

    expires_at = (
        datetime.utcnow() + timedelta(days=days_ttl) if days_ttl else None
    )

    promo = PromoCode(
        code=code,
        type="free_seconds",
        value=seconds,
        max_uses=max_uses,
        expires_at=expires_at,
        is_active=True,
    )
    session.add(promo)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        await message.answer(f"❌ Код <code>{code}</code> уже существует.", parse_mode="HTML")
        return

    logger.info(
        "admin_promo_create",
        admin_id=user.id,
        code=code,
        seconds=seconds,
        max_uses=max_uses,
        expires_at=str(expires_at),
    )

    expires_str = f"{expires_at:%d.%m.%Y}" if expires_at else "без срока"
    limit_str = f"до {max_uses} активаций" if max_uses else "без лимита"
    hours, mins = divmod(seconds // 60, 60)
    reward_str = f"{hours} ч {mins} мин" if hours else f"{mins} мин"
    await message.answer(
        f"✅ Промокод <code>{code}</code> создан.\n\n"
        f"🎁 Награда: {reward_str}\n"
        f"📊 Лимит: {limit_str}\n"
        f"⏳ Истекает: {expires_str}",
        parse_mode="HTML",
    )
