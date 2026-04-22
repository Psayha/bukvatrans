"""Send messages from Celery worker back to Telegram users.

All outbound requests use the BOT_TOKEN in the URL; error paths scrub the
token before logging to prevent accidental secret exposure.
"""
from typing import Optional

import httpx

from src.config import settings
from src.utils.logging import get_logger, mask_token

logger = get_logger(__name__)


def _api_url(method: str) -> str:
    return f"https://api.telegram.org/bot{settings.BOT_TOKEN}/{method}"


async def send_message(
    chat_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup: Optional[dict] = None,
) -> None:
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(_api_url("sendMessage"), json=payload)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(
                "tg_send_message_failed",
                chat_id=chat_id,
                error=mask_token(str(e)),
            )
            raise


async def send_document(
    chat_id: int,
    document_bytes: bytes,
    filename: str,
    caption: Optional[str] = None,
) -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        files = {"document": (filename, document_bytes, "application/octet-stream")}
        data: dict = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        try:
            response = await client.post(_api_url("sendDocument"), data=data, files=files)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(
                "tg_send_document_failed",
                chat_id=chat_id,
                filename=filename,
                error=mask_token(str(e)),
            )
            raise
