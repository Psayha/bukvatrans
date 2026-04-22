import ipaddress
import socket
from typing import Optional
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


def _is_private_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _host_is_private(host: Optional[str]) -> bool:
    """Return True if host is a private/loopback IP or resolves to one."""
    if not host:
        return True
    if _is_private_ip(host):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return True  # unresolvable → treat as unsafe
    for info in infos:
        addr = info[4][0]
        if _is_private_ip(addr):
            return True
    return False


def is_allowed_url(url: str) -> bool:
    """Return True if url belongs to a supported domain (no DNS resolution)."""
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
    host = parsed.hostname or ""
    if not host:
        return False
    domain = host.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    # Reject numeric-IP hosts outright — whitelisted domains never come as raw IPs.
    if _is_private_ip(host):
        return False
    return any(domain == d or domain.endswith("." + d) for d in SUPPORTED_DOMAINS)


def is_safe_remote_url(url: str) -> bool:
    """Strict check right before handing the URL to yt-dlp.

    Performs live DNS resolution and rejects any host that resolves to a
    private/loopback/link-local address, protecting against DNS rebinding
    and host-header tricks.
    """
    if not is_allowed_url(url):
        return False
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return not _host_is_private(parsed.hostname)


def validate_file_size(size_bytes: int) -> bool:
    """Return True if file size is within allowed limits."""
    return 0 < size_bytes <= MAX_FILE_SIZE_BYTES


def validate_mime_type(mime_type: str) -> bool:
    """Return True if MIME type is allowed."""
    return mime_type.lower() in ALLOWED_MIME_TYPES


def validate_duration(duration_seconds: int) -> bool:
    """Return True if audio duration is within allowed limits."""
    return 0 < duration_seconds <= MAX_DURATION_SECONDS
