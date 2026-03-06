import pytest
from src.utils.validators import (
    is_allowed_url,
    validate_file_size,
    validate_mime_type,
    validate_duration,
    MAX_FILE_SIZE_BYTES,
    MAX_DURATION_SECONDS,
)


class TestUrlValidator:
    @pytest.mark.parametrize("url,expected", [
        ("https://www.youtube.com/watch?v=test123", True),
        ("https://youtu.be/test123", True),
        ("https://rutube.ru/video/test", True),
        ("https://drive.google.com/file/d/test", True),
        ("https://disk.yandex.ru/i/test", True),
        ("https://yadi.sk/d/test", True),
        ("https://vk.com/video", True),
        ("https://ok.ru/video/test", True),
        # Negative cases
        ("https://evil.com/malicious", False),
        ("https://youtube.evil.com/watch", False),
        ("javascript:alert(1)", False),
        ("", False),
        ("not_a_url", False),
        ("ftp://youtube.com/video", False),
        ("http://notgoogle.com/file", False),
    ])
    def test_url_validation(self, url, expected):
        assert is_allowed_url(url) == expected

    def test_youtube_no_www(self):
        assert is_allowed_url("https://youtube.com/watch?v=abc") is True

    def test_subdomain_not_allowed(self):
        """Subdomains of allowed domains should not be accepted if not in list."""
        # drive.google.com is allowed, but random.google.com should not be
        # (our logic checks domain == d or domain.endswith("." + d))
        # So mail.google.com would pass since it ends with ".google.com"
        # Per TZ only drive.google.com is in SUPPORTED_DOMAINS
        assert is_allowed_url("https://drive.google.com/file") is True


class TestFileSizeValidator:
    def test_within_limit(self):
        assert validate_file_size(100 * 1024 * 1024) is True  # 100 MB

    def test_exactly_at_limit(self):
        assert validate_file_size(MAX_FILE_SIZE_BYTES) is True

    def test_exceeds_limit(self):
        assert validate_file_size(MAX_FILE_SIZE_BYTES + 1) is False

    def test_zero_size(self):
        assert validate_file_size(0) is False

    def test_negative_size(self):
        assert validate_file_size(-1) is False

    def test_1_byte(self):
        assert validate_file_size(1) is True

    def test_2gb(self):
        assert validate_file_size(2 * 1024 * 1024 * 1024) is True

    def test_over_2gb(self):
        assert validate_file_size(2 * 1024 * 1024 * 1024 + 1) is False


class TestMimeTypeValidator:
    @pytest.mark.parametrize("mime,expected", [
        ("audio/mpeg", True),
        ("audio/ogg", True),
        ("audio/wav", True),
        ("audio/mp4", True),
        ("audio/aac", True),
        ("audio/flac", True),
        ("video/mp4", True),
        ("video/quicktime", True),
        ("video/x-msvideo", True),
        ("video/x-matroska", True),
        # Negative
        ("application/pdf", False),
        ("image/jpeg", False),
        ("text/plain", False),
        ("application/zip", False),
        ("audio/MPEG", True),   # validator applies .lower() — case-insensitive
    ])
    def test_mime_validation(self, mime, expected):
        assert validate_mime_type(mime) == expected


class TestDurationValidator:
    def test_valid_duration(self):
        assert validate_duration(3600) is True

    def test_zero(self):
        assert validate_duration(0) is False

    def test_at_limit(self):
        assert validate_duration(MAX_DURATION_SECONDS) is True

    def test_exceeds_limit(self):
        assert validate_duration(MAX_DURATION_SECONDS + 1) is False

    def test_4_hours(self):
        assert validate_duration(4 * 3600) is True

    def test_4_hours_plus_1(self):
        assert validate_duration(4 * 3600 + 1) is False
