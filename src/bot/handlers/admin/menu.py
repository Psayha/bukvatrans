from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.handlers.admin._common import guard
from src.config import settings
from src.db.models.user import User

router = Router()


_MENU = (
    "🛠 <b>Админ-панель</b>\n\n"
    "<b>Пользователи</b>\n"
    "/admin_user ID — карточка\n"
    "/admin_balance ID SEC — начислить баланс (2FA)\n"
    "/admin_ban ID / /admin_unban ID — бан/разбан (2FA)\n\n"
    "<b>Контент</b>\n"
    "/admin_broadcast — рассылка всем (2FA)\n"
    "/admin_promo CREATE CODE SEC [MAX] [DAYS] — создать промокод\n\n"
    "<b>Инфра</b>\n"
    "/admin_stats — сводка (2FA)\n"
    "/admin_model [фильтр] — выбрать LLM-модель"
    "{testpay_block}"
)

_TESTPAY_LINE = "\n\n<b>Dev</b>\n/admin_testpay PLAN_KEY [ID] — тестовая оплата"


@router.message(Command("admin"))
async def cmd_admin(message: Message, user: User, state: FSMContext) -> None:
    if not await guard(user):
        return
    testpay = _TESTPAY_LINE if settings.ENV != "production" else ""
    await message.answer(_MENU.format(testpay_block=testpay), parse_mode="HTML")
