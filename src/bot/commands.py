"""Slash-command list shown by the Telegram client.

Called once on bot startup. Changing this module is how the BotFather
menu gets updated — no manual /setcommands needed.
"""
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

from src.utils.logging import get_logger

logger = get_logger(__name__)


# Order matters: Telegram renders the list top-to-bottom.
PUBLIC_COMMANDS: list[BotCommand] = [
    BotCommand(command="start", description="🏠 Главное меню"),
    BotCommand(command="menu", description="🏠 Главное меню"),
    BotCommand(command="subscription", description="💳 Подписка и тарифы"),
    BotCommand(command="plans", description="💎 Тарифы"),
    BotCommand(command="referral", description="🤝 Реферальная программа"),
    BotCommand(command="settings", description="⚙️ Настройки"),
    BotCommand(command="history", description="📜 Последние транскрибации"),
    BotCommand(command="promo", description="🎟 Ввести промокод"),
    BotCommand(command="support", description="💬 Поддержка"),
    BotCommand(command="about", description="ℹ️ О сервисе"),
    BotCommand(command="privacy", description="🔒 Политика ПДн"),
    BotCommand(command="terms", description="📄 Соглашение"),
    BotCommand(command="cancel", description="⏹ Отменить задачу"),
]


async def sync_bot_commands(bot: Bot) -> None:
    """Publish the PUBLIC_COMMANDS list to Telegram for all private chats."""
    try:
        await bot.set_my_commands(
            PUBLIC_COMMANDS,
            scope=BotCommandScopeAllPrivateChats(),
        )
        logger.info("bot_commands_synced count=%s", len(PUBLIC_COMMANDS))
    except Exception:
        logger.warning("bot_commands_sync_failed", exc_info=True)
