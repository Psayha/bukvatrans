from typing import Optional

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings

SUMMARY_PROMPT = """Ты — профессиональный редактор и конспектировщик.
Тебе дан текст транскрибации аудио/видео материала.

Создай структурированный конспект строго на русском языке со следующими разделами:

## 📌 Ключевая мысль
[1-2 предложения — главная идея всего материала]

## 📋 Основные тезисы
[3-7 ключевых тезиса маркированным списком]

## 💡 Важные детали
[Факты, цифры, имена, конкретные примеры из текста]

## 🗣️ Цитаты
[2-3 наиболее значимые цитаты из текста]

## ✅ Итог / Выводы
[Краткое резюме в 2-3 предложениях]

Текст транскрибации:
{text}

Важно: отвечай ТОЛЬКО конспектом, без вступлений и пояснений."""

MAX_TEXT_LENGTH = 150_000
CHUNK_SIZE = 50_000


def _prepare_text(text: str) -> str:
    """If text > 150k chars — take first/middle/last 50k with note."""
    if len(text) <= MAX_TEXT_LENGTH:
        return text
    first = text[:CHUNK_SIZE]
    mid_start = len(text) // 2 - CHUNK_SIZE // 2
    middle = text[mid_start: mid_start + CHUNK_SIZE]
    last = text[-CHUNK_SIZE:]
    return (
        first
        + "\n\n[... пропущена часть текста ...]\n\n"
        + middle
        + "\n\n[... пропущена часть текста ...]\n\n"
        + last
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=8), reraise=True)
async def generate_summary(text: str, api_key: Optional[str] = None) -> str:
    """Generate a structured summary using Claude API."""
    key = api_key or settings.CLAUDE_API_KEY
    client = anthropic.AsyncAnthropic(api_key=key)

    prepared = _prepare_text(text)
    message = await client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=2048,
        messages=[
            {"role": "user", "content": SUMMARY_PROMPT.format(text=prepared)}
        ],
    )
    return message.content[0].text
