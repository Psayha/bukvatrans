"""Send messages from Celery worker back to Telegram users."""
from typing import Optional

import httpx

from src.config import settings

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


async def send_message(
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: Optional[dict] = None,
) -> None:
    """Send a Telegram message using Bot API directly (for use from workers)."""
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    payload: dict = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()


async def send_document(
    chat_id: int,
    document_bytes: bytes,
    filename: str,
    caption: Optional[str] = None,
) -> None:
    """Send a file document to a Telegram user."""
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendDocument"
    async with httpx.AsyncClient(timeout=60) as client:
        files = {"document": (filename, document_bytes, "application/octet-stream")}
        data: dict = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        response = await client.post(url, data=data, files=files)
        response.raise_for_status()
