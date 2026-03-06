from urllib.parse import urlparse

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024   # 2 GB
MAX_DURATION_SECONDS = 4 * 3600                  # 4 hours

ALLOWED_MIME_TYPES = {
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "audio/mp4",
    "audio/aac",
    "audio/flac",
    "audio/x-m4a",
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/x-matroska",
}

SUPPORTED_DOMAINS = [
    "youtube.com",
    "youtu.be",
    "rutube.ru",
    "vk.com",
    "vkvideo.ru",
    "ok.ru",
    "drive.google.com",
    "disk.yandex.ru",
    "yadi.sk",
]


def is_allowed_url(url: str) -> bool:
    """Return True if url belongs to a supported domain."""
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.netloc:
        return False
    domain = parsed.netloc.lower()
    # Strip www. prefix
    if domain.startswith("www."):
        domain = domain[4:]
    return any(domain == d or domain.endswith("." + d) for d in SUPPORTED_DOMAINS)


def validate_file_size(size_bytes: int) -> bool:
    """Return True if file size is within allowed limits."""
    return 0 < size_bytes <= MAX_FILE_SIZE_BYTES


def validate_mime_type(mime_type: str) -> bool:
    """Return True if MIME type is allowed."""
    return mime_type.lower() in ALLOWED_MIME_TYPES


def validate_duration(duration_seconds: int) -> bool:
    """Return True if audio duration is within allowed limits."""
    return 0 < duration_seconds <= MAX_DURATION_SECONDS
