import asyncio
import uuid
import tempfile
from pathlib import Path
from typing import Optional

YDL_OPTS_BASE = {
    "format": "bestaudio/best",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "128",
    }],
    "max_filesize": 2 * 1024 * 1024 * 1024,
    "socket_timeout": 30,
    "retries": 3,
    "quiet": True,
    "no_warnings": True,
}


async def download_url(url: str, output_dir: Path) -> Path:
    """Download audio from URL using yt-dlp. Returns path to downloaded mp3."""
    import yt_dlp

    out_template = str(output_dir / f"{uuid.uuid4()}.%(ext)s")
    opts = {**YDL_OPTS_BASE, "outtmpl": out_template}

    loop = asyncio.get_event_loop()

    def _download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    filename = await loop.run_in_executor(None, _download)
    # yt-dlp adds .mp3 via postprocessor, may differ from prepare_filename
    mp3_path = Path(filename).with_suffix(".mp3")
    if mp3_path.exists():
        return mp3_path
    # Fallback: find any mp3 in output_dir
    mp3_files = list(output_dir.glob("*.mp3"))
    if mp3_files:
        return mp3_files[0]
    raise FileNotFoundError(f"Downloaded file not found in {output_dir}")
