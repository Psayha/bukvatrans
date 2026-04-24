"""Summary generation via OpenRouter (OpenAI-compatible).

OpenRouter is a thin gateway over many LLM providers (Claude / GPT /
Gemini / Llama / etc.). Swapping the model is a config change:

    OPENROUTER_MODEL=openai/gpt-4o-mini
    OPENROUTER_MODEL=google/gemini-2.5-flash
    OPENROUTER_MODEL=anthropic/claude-3.5-haiku   # default

Same code, same prompt, different upstream.

If the OpenRouter host is also geo-blocked from the server (RU/CN),
set OPENROUTER_BASE_URL to a proxy — same pattern as GROQ_API_BASE.
"""
from typing import Optional

import httpx
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
async def generate_summary(
    text: str,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Generate a structured Russian summary via OpenRouter.

    The active model is, in order:
      1. caller-supplied `model` argument (tests),
      2. runtime override from Redis (set by /admin_model),
      3. settings.OPENROUTER_MODEL (default from .env).
    """
    key = api_key or settings.OPENROUTER_API_KEY
    if model is None:
        # Lazy import to avoid a cycle if admin_model ever grew this direction.
        from src.utils.admin_model import get_active_model
        model = await get_active_model()
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    prepared = _prepare_text(text)
    url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                # Optional: OpenRouter uses these for attribution on their
                # leaderboards. Harmless but nice.
                "HTTP-Referer": "https://github.com/Psayha/bukvatrans",
                "X-Title": "bukvatrans",
            },
            json={
                "model": model,
                "max_tokens": 2048,
                "temperature": 0.3,
                "messages": [
                    {"role": "user", "content": SUMMARY_PROMPT.format(text=prepared)}
                ],
            },
        )
        response.raise_for_status()
        data = response.json()

    # OpenAI-compatible response shape.
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected OpenRouter response: {data!r}") from e
