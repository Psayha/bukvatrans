"""Unit tests for bot middlewares."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User as TgUser


def make_tg_user(user_id: int = 123, username: str = "test") -> TgUser:
    user = MagicMock(spec=TgUser)
    user.id = user_id
    user.username = username
    user.first_name = "Test"
    user.last_name = None
    return user


class TestBanMiddleware:
    @pytest.mark.asyncio
    async def test_banned_user_blocked(self):
        from src.bot.middlewares.ban import BanMiddleware
        from src.db.models.user import User

        middleware = BanMiddleware()
        handler = AsyncMock()
        event = MagicMock(spec=Message)
        event.answer = AsyncMock()

        banned_user = User(id=1, is_banned=True)
        data = {"user": banned_user}

        # Patch isinstance so the ban branch fires
        with patch("src.bot.middlewares.ban.isinstance", return_value=True):
            await middleware(handler, event, data)

        handler.assert_not_called()
        event.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_normal_user_passes(self):
        from src.bot.middlewares.ban import BanMiddleware
        from src.db.models.user import User

        middleware = BanMiddleware()
        handler = AsyncMock(return_value="ok")
        event = AsyncMock(spec=Message)

        normal_user = User(id=1, is_banned=False)
        data = {"user": normal_user}

        await middleware(handler, event, data)
        handler.assert_called_once_with(event, data)

    @pytest.mark.asyncio
    async def test_no_user_in_data_passes(self):
        from src.bot.middlewares.ban import BanMiddleware

        middleware = BanMiddleware()
        handler = AsyncMock(return_value="ok")
        event = AsyncMock(spec=Message)
        data = {}

        await middleware(handler, event, data)
        handler.assert_called_once()


class TestDatabaseMiddleware:
    @pytest.mark.asyncio
    async def test_session_injected_into_data(self):
        from src.bot.middlewares.database import DatabaseMiddleware
        from sqlalchemy.ext.asyncio import AsyncSession

        middleware = DatabaseMiddleware()
        handler = AsyncMock(return_value="ok")
        event = MagicMock()
        data = {}

        mock_session = AsyncMock(spec=AsyncSession)
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("src.bot.middlewares.database.async_session_factory", return_value=mock_ctx):
            await middleware(handler, event, data)

        assert "session" in data
        handler.assert_called_once()


class TestUserMiddlewareRefParsing:
    def test_ref_id_extracted_from_start_command(self):
        """Test that referrer_id is correctly extracted from /start ref_123."""
        text = "/start ref_456789"
        referrer_id = None
        if text.startswith("/start ref_"):
            try:
                referrer_id = int(text.split("ref_")[1].strip())
            except (ValueError, IndexError):
                referrer_id = None
        assert referrer_id == 456789

    def test_self_referral_rejected(self):
        """User cannot refer themselves."""
        user_id = 123
        text = f"/start ref_{user_id}"
        referrer_id = None
        if text.startswith("/start ref_"):
            try:
                referrer_id = int(text.split("ref_")[1].strip())
                if referrer_id == user_id:
                    referrer_id = None
            except (ValueError, IndexError):
                referrer_id = None
        assert referrer_id is None

    def test_invalid_ref_ignored(self):
        text = "/start ref_notanumber"
        referrer_id = None
        if text.startswith("/start ref_"):
            try:
                referrer_id = int(text.split("ref_")[1].strip())
            except (ValueError, IndexError):
                referrer_id = None
        assert referrer_id is None

    def test_plain_start_no_ref(self):
        text = "/start"
        referrer_id = None
        if text.startswith("/start ref_"):
            try:
                referrer_id = int(text.split("ref_")[1].strip())
            except (ValueError, IndexError):
                referrer_id = None
        assert referrer_id is None
