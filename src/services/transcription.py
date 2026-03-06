import asyncio
from pathlib import Path
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import settings

GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"


@retry(
    retry=retry_if_exception_type(httpx.HTTPStatusError),
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
        tasks = [transcribe_chunk(chunk, language=language, api_key=api_key) for chunk in chunks]
        texts = await asyncio.gather(*tasks)
        return merge_transcriptions(list(texts)), []
