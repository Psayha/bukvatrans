"""Unit tests for src/api/auth.py — pure functions only."""
import hashlib
import hmac
import time

import pytest

from src.api.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_telegram_widget,
)
from src.config import settings


class TestPasswords:
    def test_hash_and_verify(self):
        h = hash_password("mypassword")
        assert verify_password("mypassword", h) is True

    def test_wrong_password_fails(self):
        h = hash_password("correct")
        assert verify_password("wrong", h) is False

    def test_hashes_are_bcrypt(self):
        h = hash_password("secret")
        assert h != "secret"
        assert h.startswith("$2")

    def test_two_hashes_of_same_password_differ(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2

    def test_empty_string_password(self):
        h = hash_password("")
        assert verify_password("", h) is True
        assert verify_password("notempty", h) is False


class TestAccessToken:
    def test_round_trip(self):
        token = create_access_token(user_id=123)
        payload = decode_token(token)
        assert payload["sub"] == "123"
        assert payload["type"] == "access"
        assert payload["adm"] is False

    def test_admin_flag(self):
        token = create_access_token(user_id=456, is_admin=True)
        payload = decode_token(token)
        assert payload["adm"] is True

    def test_different_users_get_different_tokens(self):
        t1 = create_access_token(user_id=1)
        t2 = create_access_token(user_id=2)
        assert t1 != t2

    def test_token_has_expiry(self):
        token = create_access_token(user_id=99)
        payload = decode_token(token)
        assert "exp" in payload


class TestRefreshToken:
    def test_round_trip(self):
        token = create_refresh_token(user_id=789)
        payload = decode_token(token)
        assert payload["sub"] == "789"
        assert payload["type"] == "refresh"

    def test_is_different_from_access(self):
        access = create_access_token(user_id=1)
        refresh = create_refresh_token(user_id=1)
        assert access != refresh
        assert decode_token(access)["type"] == "access"
        assert decode_token(refresh)["type"] == "refresh"


class TestDecodeToken:
    def test_invalid_token_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid or expired token"):
            decode_token("not.a.valid.token")

    def test_tampered_signature_raises(self):
        token = create_access_token(user_id=1)
        parts = token.split(".")
        # Corrupt the signature
        tampered = parts[0] + "." + parts[1] + ".AAAA"
        with pytest.raises(ValueError):
            decode_token(tampered)

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            decode_token("")

    def test_arbitrary_string_raises(self):
        with pytest.raises(ValueError):
            decode_token("eyJ.INVALID.TOKEN")


class TestTelegramWidget:
    def _build(self, user_id=111, extra_age=0):
        auth_date = int(time.time()) - extra_age
        data = {
            "id": str(user_id),
            "first_name": "Test",
            "username": "testbot",
            "auth_date": str(auth_date),
        }
        entries = sorted(f"{k}={v}" for k, v in data.items())
        dcs = "\n".join(entries)
        secret_key = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()
        data["hash"] = hmac.new(secret_key, dcs.encode(), hashlib.sha256).hexdigest()
        return data

    def test_valid_data_passes(self):
        assert verify_telegram_widget(self._build()) is True

    def test_missing_hash_fails(self):
        assert verify_telegram_widget({}) is False

    def test_no_hash_key_fails(self):
        data = {"id": "1", "auth_date": str(int(time.time()))}
        assert verify_telegram_widget(data) is False

    def test_wrong_hash_fails(self):
        data = self._build()
        data["hash"] = "0" * 64
        assert verify_telegram_widget(data) is False

    def test_stale_auth_date_fails(self):
        # auth_date older than 86400 seconds
        data = self._build(extra_age=86401)
        # Recompute the correct hash with the stale date so only age check fails
        entries = sorted(f"{k}={v}" for k, v in data.items() if k != "hash")
        dcs = "\n".join(entries)
        sk = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()
        data["hash"] = hmac.new(sk, dcs.encode(), hashlib.sha256).hexdigest()
        assert verify_telegram_widget(data) is False

    def test_modified_field_invalidates_hash(self):
        data = self._build()
        data["first_name"] = "Hacker"  # hash was for "Test"
        assert verify_telegram_widget(data) is False
