"""Reply keyboards — the persistent grid under the chat input.

These are the main navigation of the bot. Labels are constants in
`src.bot.texts.ru` so handlers filter on them via `F.text ==`.
"""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from src.bot.texts.ru import (
    BTN_NEW,
    BTN_PLANS,
    BTN_REFERRAL,
    BTN_SETTINGS,
    BTN_SUPPORT,
)


def main_menu_kb() -> ReplyKeyboardMarkup:
    """5-button grid that sits under every chat with the bot.

    Arrangement:
        [ 📝 Новая транскрибация ]
        [ 💳 Тарифы ][ 🤝 Рефералы ]
        [ ⚙️ Настройки ][ 💬 Поддержка ]
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_NEW)],
            [KeyboardButton(text=BTN_PLANS), KeyboardButton(text=BTN_REFERRAL)],
            [KeyboardButton(text=BTN_SETTINGS), KeyboardButton(text=BTN_SUPPORT)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


MAIN_BUTTON_TEXTS: set[str] = {
    BTN_NEW,
    BTN_PLANS,
    BTN_REFERRAL,
    BTN_SETTINGS,
    BTN_SUPPORT,
}
