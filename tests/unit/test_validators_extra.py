"""Additional validator edge cases."""
import pytest
from src.utils.validators import is_allowed_url, SUPPORTED_DOMAINS


class TestUrlEdgeCases:
    def test_url_with_path_and_params(self):
        url = "https://www.youtube.com/watch?v=abc123&t=10s"
        assert is_allowed_url(url) is True

    def test_http_also_allowed(self):
        """http:// URLs should also be accepted."""
        assert is_allowed_url("http://youtube.com/watch?v=test") is True

    def test_all_supported_domains_pass(self):
        domain_urls = {
            "youtube.com": "https://youtube.com/watch?v=1",
            "youtu.be": "https://youtu.be/abc",
            "rutube.ru": "https://rutube.ru/video/xyz",
            "vk.com": "https://vk.com/video123",
            "ok.ru": "https://ok.ru/video/123",
            "drive.google.com": "https://drive.google.com/file/d/123",
            "disk.yandex.ru": "https://disk.yandex.ru/i/abc",
            "yadi.sk": "https://yadi.sk/d/xyz",
        }
        for domain, url in domain_urls.items():
            assert is_allowed_url(url) is True, f"Failed for domain: {domain}"

    def test_url_no_scheme(self):
        assert is_allowed_url("youtube.com/watch?v=test") is False

    def test_ftp_not_allowed(self):
        assert is_allowed_url("ftp://youtube.com/file") is False

    def test_data_uri_not_allowed(self):
        assert is_allowed_url("data:text/html,<script>alert(1)</script>") is False

    def test_very_long_url(self):
        url = "https://youtube.com/watch?v=" + "a" * 500
        assert is_allowed_url(url) is True

    def test_url_with_fragment(self):
        assert is_allowed_url("https://youtu.be/abc#t=120") is True

    def test_none_raises_no_error(self):
        """Empty string should return False, not raise."""
        assert is_allowed_url("") is False
