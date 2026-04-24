import asyncio
from pathlib import Path
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from src.config import settings

# Can be pointed at a Cloudflare Worker that proxies to api.groq.com when
# the host is geo-blocked from the server (common in RU/CN). See
# scripts/groq_proxy_worker.js for the worker template.
GROQ_TRANSCRIPTION_URL = f"{settings.GROQ_API_BASE.rstrip('/')}/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"


def _should_retry(exc: BaseException) -> bool:
    # Network-level hiccups (proxy blink, connection reset, DNS, read timeout)
    # — transient by nature, worth retrying.
    if isinstance(exc, httpx.TransportError):
        return True
    # HTTP-level: retry 5xx (upstream transient) and 429 (rate limit — the
    # server is explicitly asking us to back off and try again). Other 4xx
    # (400/401/413) mean our request is wrong and won't fix itself.
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return False


@retry(
    retry=retry_if_exception(_should_retry),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True,
)
async def transcribe_chunk(
    audio_path: Path,
    language: str = "ru",
    api_key: Optional[str] = None,
) -> str:
    """Transcribe a single audio chunk via Groq Whisper API."""
    key = api_key or settings.GROQ_API_KEY
    async with httpx.AsyncClient(timeout=120) as client:
        with open(audio_path, "rb") as f:
            response = await client.post(
                GROQ_TRANSCRIPTION_URL,
                headers={"Authorization": f"Bearer {key}"},
                files={"file": (audio_path.name, f, "audio/mpeg")},
                data={
                    "model": GROQ_MODEL,
                    "language": language,
                    "response_format": "verbose_json",
                    "temperature": "0",
                },
            )
        response.raise_for_status()
        data = response.json()
        return data.get("text", "")


# Cap concurrent Groq requests so long transcriptions don't trip the
# per-minute rate limit. Groq's free tier is ~20 RPM on whisper-large-v3-turbo.
GROQ_MAX_CONCURRENCY = 5


async def transcribe_audio(
    audio_path: Path,
    language: str = "ru",
    api_key: Optional[str] = None,
) -> tuple[str, list[dict]]:
    """
    Transcribe audio file. Splits into chunks if > 25 MB.
    Returns (full_text, segments_list).
    """
    from src.services.audio_processor import needs_chunking, split_audio, merge_transcriptions
    import tempfile

    if not needs_chunking(audio_path):
        text = await transcribe_chunk(audio_path, language=language, api_key=api_key)
        return text, []

    with tempfile.TemporaryDirectory() as tmp_dir:
        chunks = await split_audio(audio_path, Path(tmp_dir))
        # Bounded concurrency — Semaphore is bound to the current event loop,
        # which matches the per-task loop created by the Celery worker.
        sem = asyncio.Semaphore(GROQ_MAX_CONCURRENCY)

        async def _bounded(chunk):
            async with sem:
                return await transcribe_chunk(chunk, language=language, api_key=api_key)

        texts = await asyncio.gather(*(_bounded(c) for c in chunks))
        return merge_transcriptions(list(texts)), []
