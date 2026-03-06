"""Tests for services (notification, downloader, storage) and utils (logging, states)."""
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# Mock boto3 since it's not installed in test environment
if "boto3" not in sys.modules:
    _boto3_mock = MagicMock()
    _boto3_mock.client.return_value = MagicMock()
    sys.modules["boto3"] = _boto3_mock
    sys.modules["botocore"] = MagicMock()
    sys.modules["botocore.client"] = MagicMock()

# Mock redis since it's not installed in test environment
if "redis" not in sys.modules:
    _redis_mock = MagicMock()
    sys.modules["redis"] = _redis_mock
    sys.modules["redis.asyncio"] = _redis_mock


# ---------------------------------------------------------------------------
# notification.py
# ---------------------------------------------------------------------------

class TestNotification:
    @pytest.mark.asyncio
    async def test_send_message_success(self):
        from src.services.notification import send_message

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.services.notification.httpx.AsyncClient", return_value=mock_client):
            with patch("src.services.notification.settings") as mock_settings:
                mock_settings.BOT_TOKEN = "123456:ABC"
                await send_message(chat_id=100, text="Hello!")

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["chat_id"] == 100
        assert call_kwargs["json"]["text"] == "Hello!"

    @pytest.mark.asyncio
    async def test_send_message_with_markup(self):
        from src.services.notification import send_message

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        markup = {"inline_keyboard": [[{"text": "Click", "callback_data": "x"}]]}

        with patch("src.services.notification.httpx.AsyncClient", return_value=mock_client):
            with patch("src.services.notification.settings") as mock_settings:
                mock_settings.BOT_TOKEN = "123456:ABC"
                await send_message(chat_id=100, text="Hello!", reply_markup=markup)

        call_kwargs = mock_client.post.call_args[1]
        assert "reply_markup" in call_kwargs["json"]

    @pytest.mark.asyncio
    async def test_send_document_success(self):
        from src.services.notification import send_document

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.services.notification.httpx.AsyncClient", return_value=mock_client):
            with patch("src.services.notification.settings") as mock_settings:
                mock_settings.BOT_TOKEN = "123456:ABC"
                await send_document(
                    chat_id=100,
                    document_bytes=b"fake content",
                    filename="test.docx",
                    caption="Test caption",
                )

        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["data"]["chat_id"] == "100"

    @pytest.mark.asyncio
    async def test_send_document_no_caption(self):
        from src.services.notification import send_document

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.services.notification.httpx.AsyncClient", return_value=mock_client):
            with patch("src.services.notification.settings") as mock_settings:
                mock_settings.BOT_TOKEN = "123456:ABC"
                await send_document(
                    chat_id=200,
                    document_bytes=b"content",
                    filename="doc.txt",
                )

        call_kwargs = mock_client.post.call_args[1]
        assert "caption" not in call_kwargs["data"]


# ---------------------------------------------------------------------------
# downloader.py
# ---------------------------------------------------------------------------

class TestDownloader:
    def test_ydl_opts_base_structure(self):
        from src.services.downloader import YDL_OPTS_BASE
        assert YDL_OPTS_BASE["format"] == "bestaudio/best"
        assert YDL_OPTS_BASE["max_filesize"] == 2 * 1024 * 1024 * 1024
        assert len(YDL_OPTS_BASE["postprocessors"]) == 1
        assert YDL_OPTS_BASE["postprocessors"][0]["preferredcodec"] == "mp3"

    @pytest.mark.asyncio
    async def test_download_url_returns_mp3_path(self, tmp_path):
        from src.services.downloader import download_url

        # Create a fake mp3 file in tmp_path
        mp3_file = tmp_path / "audio.mp3"
        mp3_file.write_bytes(b"fake mp3 data")

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info = MagicMock(return_value={"id": "abc"})
        mock_ydl_instance.prepare_filename = MagicMock(return_value=str(tmp_path / "audio.webm"))
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=None)

        mock_yt_dlp = MagicMock()
        mock_yt_dlp.YoutubeDL = MagicMock(return_value=mock_ydl_instance)

        with patch.dict("sys.modules", {"yt_dlp": mock_yt_dlp}):
            result = await download_url("https://youtube.com/watch?v=test", tmp_path)

        assert result.suffix == ".mp3"
        assert result.exists()

    @pytest.mark.asyncio
    async def test_download_url_fallback_glob(self, tmp_path):
        from src.services.downloader import download_url

        # mp3 file in tmp but with different name
        mp3_file = tmp_path / "different_name.mp3"
        mp3_file.write_bytes(b"fake mp3")

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info = MagicMock(return_value={"id": "abc"})
        mock_ydl_instance.prepare_filename = MagicMock(
            return_value=str(tmp_path / "original_name.webm")
        )
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=None)

        mock_yt_dlp = MagicMock()
        mock_yt_dlp.YoutubeDL = MagicMock(return_value=mock_ydl_instance)

        with patch.dict("sys.modules", {"yt_dlp": mock_yt_dlp}):
            result = await download_url("https://youtube.com/watch?v=test", tmp_path)

        assert result.suffix == ".mp3"

    @pytest.mark.asyncio
    async def test_download_url_raises_when_no_file(self, tmp_path):
        from src.services.downloader import download_url

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info = MagicMock(return_value={"id": "abc"})
        mock_ydl_instance.prepare_filename = MagicMock(
            return_value=str(tmp_path / "audio.webm")
        )
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=None)

        mock_yt_dlp = MagicMock()
        mock_yt_dlp.YoutubeDL = MagicMock(return_value=mock_ydl_instance)

        with patch.dict("sys.modules", {"yt_dlp": mock_yt_dlp}):
            with pytest.raises(FileNotFoundError):
                await download_url("https://youtube.com/watch?v=test", tmp_path)


# ---------------------------------------------------------------------------
# storage.py
# ---------------------------------------------------------------------------

class TestStorage:
    def test_get_client_creates_boto3_client(self):
        from src.services import storage

        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        with patch("src.services.storage.boto3", mock_boto3):
            with patch("src.services.storage.settings") as mock_settings:
                mock_settings.S3_ENDPOINT = "https://s3.example.com"
                mock_settings.S3_ACCESS_KEY = "access"
                mock_settings.S3_SECRET_KEY = "secret"
                client = storage._get_client()

        mock_boto3.client.assert_called_once_with(
            "s3",
            endpoint_url="https://s3.example.com",
            aws_access_key_id="access",
            aws_secret_access_key="secret",
            config=mock_boto3.client.call_args[1]["config"],
        )

    def test_s3_ttl_constants(self):
        from src.services.storage import S3_TTL_HOURS, PRESIGNED_URL_TTL_SECONDS
        assert S3_TTL_HOURS == 24
        assert PRESIGNED_URL_TTL_SECONDS == 3600

    @pytest.mark.asyncio
    async def test_upload_file(self, tmp_path):
        from src.services import storage

        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")

        mock_client = MagicMock()
        mock_client.upload_file = MagicMock()

        with patch("src.services.storage._get_client", return_value=mock_client):
            with patch("src.services.storage.settings") as mock_settings:
                mock_settings.S3_BUCKET = "test-bucket"
                key = await storage.upload_file(test_file, "text/plain")

        assert key.startswith("transcriptions/")
        assert key.endswith("test.txt")
        mock_client.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_presigned_url(self):
        from src.services import storage

        mock_client = MagicMock()
        mock_client.generate_presigned_url = MagicMock(
            return_value="https://s3.example.com/presigned?sig=abc"
        )

        with patch("src.services.storage._get_client", return_value=mock_client):
            with patch("src.services.storage.settings") as mock_settings:
                mock_settings.S3_BUCKET = "test-bucket"
                url = await storage.get_presigned_url("transcriptions/abc/file.txt")

        assert "presigned" in url or "s3.example.com" in url
        mock_client.generate_presigned_url.assert_called_once()


# ---------------------------------------------------------------------------
# utils/logging.py
# ---------------------------------------------------------------------------

class TestLogging:
    def test_is_sentry_configured_false_when_no_dsn(self):
        from src.utils.logging import _is_sentry_configured
        import sentry_sdk

        # Ensure sentry is not initialized with a DSN
        with patch.object(sentry_sdk, "get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.dsn = None
            mock_get_client.return_value = mock_client
            result = _is_sentry_configured()

        assert result is False

    def test_is_sentry_configured_true_when_dsn_set(self):
        from src.utils.logging import _is_sentry_configured
        import sentry_sdk

        with patch.object(sentry_sdk, "get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.dsn = "https://key@sentry.io/123"
            mock_get_client.return_value = mock_client
            result = _is_sentry_configured()

        assert result is True

    def test_setup_logging_without_sentry_dsn(self):
        from src.utils.logging import setup_logging

        with patch("src.utils.logging._is_sentry_configured", return_value=False):
            with patch("src.config.settings") as mock_settings:
                mock_settings.SENTRY_DSN = None
                with patch("logging.basicConfig") as mock_basicconfig:
                    setup_logging()

        mock_basicconfig.assert_called_once()

    def test_setup_logging_already_configured(self):
        from src.utils.logging import setup_logging
        import sentry_sdk

        with patch("src.utils.logging._is_sentry_configured", return_value=True):
            with patch("logging.basicConfig") as mock_basicconfig:
                with patch.object(sentry_sdk, "init") as mock_init:
                    setup_logging()

        mock_init.assert_not_called()
        mock_basicconfig.assert_called_once()

    def test_setup_logging_initializes_sentry_when_dsn_present(self):
        from src.utils.logging import setup_logging
        import sentry_sdk

        with patch("src.utils.logging._is_sentry_configured", return_value=False):
            with patch("src.config.settings") as mock_settings:
                mock_settings.SENTRY_DSN = "https://key@sentry.io/123"
                mock_settings.ENV = "test"
                with patch.object(sentry_sdk, "init") as mock_init:
                    with patch("logging.basicConfig"):
                        setup_logging()

        mock_init.assert_called_once()


# ---------------------------------------------------------------------------
# bot/states.py
# ---------------------------------------------------------------------------

class TestStates:
    def test_language_select_state(self):
        from src.bot.states import LanguageSelect
        assert hasattr(LanguageSelect, "waiting_language")

    def test_payment_flow_states(self):
        from src.bot.states import PaymentFlow
        assert hasattr(PaymentFlow, "selecting_plan")
        assert hasattr(PaymentFlow, "selecting_period")
        assert hasattr(PaymentFlow, "awaiting_payment")

    def test_promo_flow_state(self):
        from src.bot.states import PromoFlow
        assert hasattr(PromoFlow, "waiting_code")

    def test_admin_flow_states(self):
        from src.bot.states import AdminFlow
        assert hasattr(AdminFlow, "main_menu")
        assert hasattr(AdminFlow, "broadcast_message")
        assert hasattr(AdminFlow, "user_lookup")
        assert hasattr(AdminFlow, "add_balance")


# ---------------------------------------------------------------------------
# bot/middlewares/user.py
# ---------------------------------------------------------------------------

class TestUserMiddleware:
    @pytest.mark.asyncio
    async def test_no_tg_user_passes_through(self):
        from src.bot.middlewares.user import UserMiddleware
        from aiogram.types import Update

        middleware = UserMiddleware()
        handler = AsyncMock(return_value="ok")

        # Update with no message or callback
        event = MagicMock(spec=Update)
        event.message = None
        event.callback_query = None

        result = await middleware(handler, event, {})
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_from_message_injected(self):
        from src.bot.middlewares.user import UserMiddleware
        from aiogram.types import Update, Message
        from src.db.models.user import User

        middleware = UserMiddleware()
        handler = AsyncMock(return_value="ok")

        tg_user = MagicMock(
            id=111,
            username="alice",
            first_name="Alice",
            last_name=None,
        )

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = tg_user
        mock_message.text = "/start"

        event = MagicMock(spec=Update)
        event.message = mock_message
        event.callback_query = None

        db_user = User(id=111, username="alice", first_name="Alice")
        mock_session = AsyncMock()
        data = {"session": mock_session}

        with patch(
            "src.bot.middlewares.user.get_or_create_user",
            return_value=(db_user, True),
        ):
            await middleware(handler, event, data)

        assert data["user"] is db_user
        assert data["is_new_user"] is True
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_from_callback_injected(self):
        from src.bot.middlewares.user import UserMiddleware
        from aiogram.types import Update, CallbackQuery
        from src.db.models.user import User

        middleware = UserMiddleware()
        handler = AsyncMock(return_value="ok")

        tg_user = MagicMock(
            id=222,
            username="bob",
            first_name="Bob",
            last_name="Smith",
        )

        mock_callback = MagicMock(spec=CallbackQuery)
        mock_callback.from_user = tg_user

        event = MagicMock(spec=Update)
        event.message = None
        event.callback_query = mock_callback

        db_user = User(id=222, username="bob", first_name="Bob")
        mock_session = AsyncMock()
        data = {"session": mock_session}

        with patch(
            "src.bot.middlewares.user.get_or_create_user",
            return_value=(db_user, False),
        ):
            await middleware(handler, event, data)

        assert data["user"] is db_user
        assert data["is_new_user"] is False

    @pytest.mark.asyncio
    async def test_ref_extracted_from_start(self):
        from src.bot.middlewares.user import UserMiddleware
        from aiogram.types import Update, Message
        from src.db.models.user import User

        middleware = UserMiddleware()
        handler = AsyncMock(return_value="ok")

        tg_user = MagicMock(id=333, username="carol", first_name="Carol", last_name=None)

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = tg_user
        mock_message.text = "/start ref_111"

        event = MagicMock(spec=Update)
        event.message = mock_message
        event.callback_query = None

        db_user = User(id=333, username="carol", first_name="Carol")
        mock_session = AsyncMock()
        data = {"session": mock_session}

        captured = {}

        async def capture_call(*args, **kwargs):
            captured.update(kwargs)
            return db_user, True

        with patch(
            "src.bot.middlewares.user.get_or_create_user",
            side_effect=capture_call,
        ):
            await middleware(handler, event, data)

        assert captured.get("referrer_id") == 111

    @pytest.mark.asyncio
    async def test_self_ref_rejected(self):
        from src.bot.middlewares.user import UserMiddleware
        from aiogram.types import Update, Message
        from src.db.models.user import User

        middleware = UserMiddleware()
        handler = AsyncMock(return_value="ok")

        tg_user = MagicMock(id=444, username="dave", first_name="Dave", last_name=None)

        mock_message = MagicMock(spec=Message)
        mock_message.from_user = tg_user
        mock_message.text = "/start ref_444"  # same as own ID

        event = MagicMock(spec=Update)
        event.message = mock_message
        event.callback_query = None

        db_user = User(id=444, username="dave", first_name="Dave")
        mock_session = AsyncMock()
        data = {"session": mock_session}

        captured = {}

        async def capture_call(*args, **kwargs):
            captured.update(kwargs)
            return db_user, True

        with patch(
            "src.bot.middlewares.user.get_or_create_user",
            side_effect=capture_call,
        ):
            await middleware(handler, event, data)

        assert captured.get("referrer_id") is None
