"""Inline keyboards used across handlers.

Reply keyboards (the persistent ones under the chat input) live in
`src/bot/keyboards/reply.py` — those are the main nav.
"""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.services.billing import PLANS, TOPUP_OPTIONS


def transcription_result_kb(
    transcription_id: str, has_video: bool = False
) -> InlineKeyboardMarkup:
    """Appears under every finished transcription.

    The 💬 AI chat button is always shown — it's a core "sticky" feature.
    """
    buttons = [
        [
            InlineKeyboardButton(text="📋 Конспект", callback_data=f"summary:{transcription_id}"),
            InlineKeyboardButton(text="📄 DOCX", callback_data=f"docx:{transcription_id}"),
        ],
        [
            InlineKeyboardButton(text="💬 Спросить ИИ", callback_data=f"ai_chat:{transcription_id}"),
        ],
    ]
    if has_video:
        buttons.insert(1, [
            InlineKeyboardButton(text="📑 SRT субтитры", callback_data=f"srt:{transcription_id}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subscribe_kb() -> InlineKeyboardMarkup:
    """Plan picker: one card per duration. `recommended` plan gets 🔥 markers."""
    rows: list[list[InlineKeyboardButton]] = []
    for key, plan in PLANS.items():
        prefix = "🔥 " if plan.get("recommended") else ""
        suffix = " 🔥" if plan.get("recommended") else ""
        rows.append([
            InlineKeyboardButton(
                text=f"{prefix}{plan['label']} — {plan['price_rub']:.0f} ₽{suffix}",
                callback_data=f"plan:{key}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text="💰 Разовое пополнение", callback_data="topup:menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topup_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{option['seconds'] // 3600} ч — {option['price_rub']:.0f} ₽",
            callback_data=f"topup:{key}",
        )]
        for key, option in TOPUP_OPTIONS.items()
    ]
    rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="topup:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def payment_link_kb(payment_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
    ])


# 14 languages + auto, paginated 9 per screen.
_AUDIO_LANGUAGES: list[tuple[str, str]] = [
    ("🔍 Авто", "auto"),
    ("🇷🇺 Русский", "ru"),
    ("🇬🇧 English", "en"),
    ("🇺🇦 Українська", "uk"),
    ("🇰🇿 Қазақша", "kk"),
    ("🇩🇪 Deutsch", "de"),
    ("🇫🇷 Français", "fr"),
    ("🇪🇸 Español", "es"),
    ("🇮🇹 Italiano", "it"),
    ("🇵🇹 Português", "pt"),
    ("🇨🇳 中文", "zh"),
    ("🇯🇵 日本語", "ja"),
    ("🇮🇳 हिन्दी", "hi"),
    ("🇹🇷 Türkçe", "tr"),
    ("🇳🇱 Nederlands", "nl"),
]

_LANG_PAGE_SIZE = 9


def language_kb(page: int = 0) -> InlineKeyboardMarkup:
    start = page * _LANG_PAGE_SIZE
    chunk = _AUDIO_LANGUAGES[start : start + _LANG_PAGE_SIZE]
    rows: list[list[InlineKeyboardButton]] = []
    # 3-column grid.
    for i in range(0, len(chunk), 3):
        rows.append([
            InlineKeyboardButton(text=name, callback_data=f"lang:{code}")
            for name, code in chunk[i : i + 3]
        ])
    # Pagination row.
    total_pages = (len(_AUDIO_LANGUAGES) + _LANG_PAGE_SIZE - 1) // _LANG_PAGE_SIZE
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"langpage:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"langpage:{page + 1}"))
    rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Назад в настройки", callback_data="settings:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
