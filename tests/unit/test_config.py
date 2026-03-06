"""Tests for application config."""
import pytest
from unittest.mock import patch


class TestSettings:
    def test_admin_ids_parsed(self):
        from src.config import Settings
        s = Settings(ADMIN_IDS="123,456,789")
        assert s.admin_ids_list == [123, 456, 789]

    def test_admin_ids_empty(self):
        from src.config import Settings
        s = Settings(ADMIN_IDS="")
        assert s.admin_ids_list == []

    def test_admin_ids_single(self):
        from src.config import Settings
        s = Settings(ADMIN_IDS="12345")
        assert s.admin_ids_list == [12345]

    def test_admin_ids_with_spaces(self):
        from src.config import Settings
        s = Settings(ADMIN_IDS="123, 456 , 789")
        assert s.admin_ids_list == [123, 456, 789]

    def test_default_database_url(self):
        from src.config import Settings
        s = Settings()
        assert "sqlite" in s.DATABASE_URL or "postgresql" in s.DATABASE_URL

    def test_default_env(self):
        from src.config import Settings
        s = Settings()
        assert s.ENV in ("development", "production", "staging", "test")
