"""Tests for URL source type detection logic."""
import pytest


def detect_source_type(url: str) -> str:
    """Mirror of the logic in src/bot/handlers/links.py."""
    from urllib.parse import urlparse
    URL_SOURCE_MAP = {
        "youtube.com": "youtube",
        "youtu.be": "youtube",
        "rutube.ru": "rutube",
        "drive.google.com": "gdrive",
        "disk.yandex.ru": "yadisk",
        "yadi.sk": "yadisk",
        "vk.com": "vk",
        "vkvideo.ru": "vk",
        "ok.ru": "ok",
    }
    domain = urlparse(url).netloc.lower().replace("www.", "")
    for d, source in URL_SOURCE_MAP.items():
        if domain == d or domain.endswith("." + d):
            return source
    return "youtube"


class TestUrlSourceDetection:
    @pytest.mark.parametrize("url,expected", [
        ("https://youtube.com/watch?v=abc", "youtube"),
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://youtu.be/abc", "youtube"),
        ("https://rutube.ru/video/xyz", "rutube"),
        ("https://drive.google.com/file/d/1", "gdrive"),
        ("https://disk.yandex.ru/i/abc", "yadisk"),
        ("https://yadi.sk/d/abc", "yadisk"),
        ("https://vk.com/video", "vk"),
        ("https://vkvideo.ru/abc", "vk"),
        ("https://ok.ru/video/1", "ok"),
    ])
    def test_source_type_detection(self, url, expected):
        assert detect_source_type(url) == expected
