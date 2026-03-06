from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User
from src.db.repositories.user import get_user, add_balance
from src.bot.states import AdminFlow
from src.config import settings

router = Router()


def is_admin(user: User) -> bool:
    return user.is_admin or user.id in settings.admin_ids_list


@router.message(Command("admin"))
async def cmd_admin(message: Message, user: User, state: FSMContext) -> None:
    if not is_admin(user):
        return
    await message.answer(
        "🛠 <b>Админ-панель</b>\n\n"
        "/admin_balance USER_ID SECONDS — добавить баланс\n"
        "/admin_ban USER_ID — забанить\n"
        "/admin_stats — статистика",
        parse_mode="HTML",
    )


@router.message(Command("admin_balance"))
async def cmd_admin_balance(
    message: Message, user: User, session: AsyncSession
) -> None:
    if not is_admin(user):
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Использование: /admin_balance USER_ID SECONDS")
        return
    try:
        target_id = int(parts[1])
        seconds = int(parts[2])
    except ValueError:
        await message.answer("Неверные аргументы.")
        return

    target = await get_user(target_id, session)
    if not target:
        await message.answer(f"Пользователь {target_id} не найден.")
        return

    await add_balance(target_id, seconds, session)
    await message.answer(f"✅ Добавлено {seconds} сек пользователю {target_id}.")


@router.message(Command("admin_ban"))
async def cmd_admin_ban(
    message: Message, user: User, session: AsyncSession
) -> None:
    if not is_admin(user):
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /admin_ban USER_ID")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("Неверный ID.")
        return

    target = await get_user(target_id, session)
    if not target:
        await message.answer(f"Пользователь {target_id} не найден.")
        return

    target.is_banned = True
    await session.commit()
    await message.answer(f"🚫 Пользователь {target_id} заблокирован.")
