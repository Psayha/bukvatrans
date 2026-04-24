"""Unit tests for webhook IP validation and business logic."""
import pytest
from src.api.webhooks import _is_yukassa_ip


class TestYukassaIPEdgeCases:
    @pytest.mark.parametrize("ip,expected", [
        # Valid single IPs
        ("77.75.156.11", True),
        ("77.75.156.35", True),
        # Valid subnet IPs
        ("185.71.76.1", True),
        ("185.71.76.31", True),
        ("185.71.77.1", True),
        ("77.75.153.1", True),
        ("77.75.154.129", True),
        # Invalid IPs
        ("1.2.3.4", False),
        ("192.168.1.1", False),
        ("10.0.0.1", False),
        ("0.0.0.0", False),
        ("255.255.255.255", False),
        # Edge cases
        ("", False),
        ("not-an-ip", False),
        ("999.999.999.999", False),
    ])
    def test_ip_validation(self, ip, expected):
        assert _is_yukassa_ip(ip) == expected

    def test_subnet_boundary_185_71_76(self):
        """185.71.76.0/27 = .0 to .31"""
        assert _is_yukassa_ip("185.71.76.0") is True
        assert _is_yukassa_ip("185.71.76.31") is True
        assert _is_yukassa_ip("185.71.76.32") is False

    def test_subnet_boundary_185_71_77(self):
        """185.71.77.0/27 = .0 to .31"""
        assert _is_yukassa_ip("185.71.77.0") is True
        assert _is_yukassa_ip("185.71.77.31") is True
        assert _is_yukassa_ip("185.71.77.32") is False


class TestWebhookHelpers:
    def test_all_plan_keys_parse(self):
        # Plan keys are now stored verbatim in Subscription.plan — no split.
        from src.services.billing import PLANS
        assert "unlimited_30d" in PLANS
        assert PLANS["unlimited_30d"]["period_days"] == 30

    def test_metadata_user_id_parsing(self):
        metadata = {"user_id": "123456789", "plan_key": "basic_monthly"}
        user_id = int(metadata.get("user_id", 0))
        assert user_id == 123456789

    def test_metadata_missing_user_id(self):
        metadata = {}
        user_id = int(metadata.get("user_id", 0))
        assert user_id == 0
