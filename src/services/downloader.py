import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlparse

from src.config import settings
from src.utils.validators import is_safe_remote_url

def _ydl_opts() -> dict:
    opts: dict = {
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
        "noplaylist": True,
        "external_downloader": None,
        "nocheckcertificate": False,
    }
    if settings.YDL_PROXY:
        opts["proxy"] = settings.YDL_PROXY
    return opts

# Dedicated pool so yt-dlp doesn't starve the default 32-thread executor.
_YDL_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ytdl")


class UnsafeURLError(ValueError):
    """Raised when a URL is not on the allow-list or resolves to a private host."""


class URLTooLargeError(ValueError):
    """Raised when the remote file exceeds the size/duration limit."""


async def _run_ydl(func):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_YDL_EXECUTOR, func)


async def probe_url(url: str) -> dict:
    """Fetch metadata WITHOUT downloading. Raises UnsafeURLError if disallowed."""
    if not is_safe_remote_url(url):
        raise UnsafeURLError("URL is not allowed")

    import yt_dlp

    domain = urlparse(url).netloc

    def _probe() -> dict:
        errors: list[str] = []

        class _ErrLogger:
            def debug(self, msg): pass
            def warning(self, msg): pass
            def error(self, msg): errors.append(msg)

        opts = {**_ydl_opts(), "skip_download": True, "logger": _ErrLogger()}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and "entries" in info and info["entries"]:
                    info = info["entries"][0]
                return info or {}
        except yt_dlp.utils.DownloadError as e:
            detail = str(e).removeprefix("ERROR: ").strip()
            suffix = f" | yt-dlp errors: {'; '.join(errors)}" if errors else ""
            raise RuntimeError(f"[{domain}] {detail}{suffix}") from e

    try:
        info = await asyncio.wait_for(_run_ydl(_probe), timeout=60)
    except asyncio.TimeoutError as e:
        raise TimeoutError(
            f"Probe timeout (60s): {domain} не ответил — "
            "сервис недоступен, требует авторизацию или заблокировал запрос"
        ) from e
    except RuntimeError as e:
        raise RuntimeError(str(e)) from e

    duration = int(info.get("duration") or 0)
    filesize = int(
        info.get("filesize")
        or info.get("filesize_approx")
        or 0
    )

    if duration and duration > settings.MAX_URL_DURATION_SECONDS:
        raise URLTooLargeError(
            f"Duration {duration}s exceeds limit {settings.MAX_URL_DURATION_SECONDS}s"
        )
    if filesize and filesize > settings.MAX_URL_FILESIZE_BYTES:
        raise URLTooLargeError(
            f"Filesize {filesize}B exceeds limit {settings.MAX_URL_FILESIZE_BYTES}B"
        )

    return {"duration": duration, "filesize": filesize, "title": info.get("title", "")}


async def download_url(url: str, output_dir: Path) -> Path:
    """Download audio from URL using yt-dlp. Returns path to downloaded mp3.

    Validates the URL is on the allow-list and does not resolve to a private
    host, pre-probes for size/duration, then invokes yt-dlp with a hard timeout
    to prevent runaway downloads.
    """
    if not is_safe_remote_url(url):
        raise UnsafeURLError("URL is not allowed")

    # Pre-flight probe — cheaper than a half-completed download if the video
    # is too big. Hard limits are also enforced via `max_filesize` below.
    await probe_url(url)

    import yt_dlp

    out_template = str(output_dir / f"{uuid.uuid4()}.%(ext)s")
    opts = {
        **_ydl_opts(),
        "outtmpl": out_template,
        "max_filesize": settings.MAX_URL_FILESIZE_BYTES,
    }

    domain = urlparse(url).netloc

    def _download() -> str:
        errors: list[str] = []

        class _ErrLogger:
            def debug(self, msg): pass
            def warning(self, msg): pass
            def error(self, msg): errors.append(msg)

        dl_opts = {**opts, "logger": _ErrLogger()}
        try:
            with yt_dlp.YoutubeDL(dl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info and "entries" in info and info["entries"]:
                    info = info["entries"][0]
                return ydl.prepare_filename(info)
        except yt_dlp.utils.DownloadError as e:
            detail = str(e).removeprefix("ERROR: ").strip()
            suffix = f" | yt-dlp errors: {'; '.join(errors)}" if errors else ""
            raise RuntimeError(f"[{domain}] {detail}{suffix}") from e

    try:
        filename = await asyncio.wait_for(
            _run_ydl(_download),
            timeout=settings.CELERY_SOFT_TIME_LIMIT - 60,
        )
    except asyncio.TimeoutError as e:
        limit = settings.CELERY_SOFT_TIME_LIMIT - 60
        raise TimeoutError(f"Download timeout ({limit}s): {domain}") from e
    except RuntimeError as e:
        raise RuntimeError(str(e)) from e

    mp3_path = Path(filename).with_suffix(".mp3")
    if mp3_path.exists():
        return mp3_path
    mp3_files = list(output_dir.glob("*.mp3"))
    if mp3_files:
        return mp3_files[0]
    raise FileNotFoundError(f"Downloaded file not found in {output_dir}")
