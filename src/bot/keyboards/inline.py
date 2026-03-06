from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def transcription_result_kb(transcription_id: str, has_video: bool = False) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📋 Конспект", callback_data=f"summary:{transcription_id}"),
            InlineKeyboardButton(text="📄 DOCX", callback_data=f"docx:{transcription_id}"),
        ],
    ]
    if has_video:
        buttons.append([
            InlineKeyboardButton(text="📑 SRT субтитры", callback_data=f"srt:{transcription_id}"),
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subscribe_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Базовый — 649₽/мес", callback_data="plan:basic_monthly"),
            InlineKeyboardButton(text="Базовый — 3890₽/год", callback_data="plan:basic_yearly"),
        ],
        [
            InlineKeyboardButton(text="Про — 1449₽/мес", callback_data="plan:pro_monthly"),
            InlineKeyboardButton(text="Про — 8690₽/год", callback_data="plan:pro_yearly"),
        ],
        [
            InlineKeyboardButton(text="💰 Разовое пополнение", callback_data="topup:menu"),
        ],
    ])


def topup_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="2 ч — 99₽", callback_data="topup:topup_99")],
        [InlineKeyboardButton(text="7 ч — 299₽", callback_data="topup:topup_299")],
        [InlineKeyboardButton(text="12 ч — 499₽", callback_data="topup:topup_499")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="topup:back")],
    ])


def payment_link_kb(payment_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
    ])


def language_kb() -> InlineKeyboardMarkup:
    languages = [
        ("🇷🇺 Русский", "ru"),
        ("🇬🇧 English", "en"),
        ("🇺🇦 Українська", "uk"),
        ("🇩🇪 Deutsch", "de"),
        ("🇫🇷 Français", "fr"),
        ("🔍 Авто", "auto"),
    ]
    rows = []
    for i in range(0, len(languages), 2):
        row = [
            InlineKeyboardButton(text=name, callback_data=f"lang:{code}")
            for name, code in languages[i:i+2]
        ]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)
