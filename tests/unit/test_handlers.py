"""Unit tests for all bot handlers — call functions directly with mocked objects."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery

from src.db.models.user import User
from src.db.models.subscription import Subscription
from src.db.models.transcription import Transcription
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(
    user_id=123,
    is_admin=False,
    is_banned=False,
    balance_seconds=7200,
    free_uses_left=0,
    subscriptions=None,
):
    u = User(
        id=user_id,
        username="testuser",
        first_name="Test",
        last_name="User",
        is_admin=is_admin,
        is_banned=is_banned,
        balance_seconds=balance_seconds,
        free_uses_left=free_uses_left,
    )
    u.subscriptions = subscriptions or []
    return u


def make_message(text="", user_id=123):
    msg = AsyncMock(spec=Message)
    msg.text = text
    msg.from_user = MagicMock(id=user_id, username="testuser")
    msg.bot = AsyncMock()
    msg.bot.get_me = AsyncMock(return_value=MagicMock(username="testbot"))
    msg.answer = AsyncMock()
    return msg


def make_callback(data="", user_id=123):
    cb = AsyncMock(spec=CallbackQuery)
    cb.data = data
    cb.from_user = MagicMock(id=user_id)
    cb.message = AsyncMock()
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    return cb


# ---------------------------------------------------------------------------
# Start handler
# ---------------------------------------------------------------------------

class TestStartHandler:
    @pytest.mark.asyncio
    async def test_cmd_start_new_user(self):
        from src.bot.handlers.start import cmd_start
        msg = make_message("/start")
        user = make_user(free_uses_left=3)
        await cmd_start(msg, user=user, is_new_user=True)
        msg.answer.assert_called_once()
        call_kwargs = msg.answer.call_args
        assert "HTML" in str(call_kwargs)

    @pytest.mark.asyncio
    async def test_cmd_start_existing_user(self):
        from src.bot.handlers.start import cmd_start
        msg = make_message("/start")
        user = make_user(balance_seconds=3600, free_uses_left=0)
        await cmd_start(msg, user=user, is_new_user=False)
        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_help(self):
        from src.bot.handlers.start import cmd_help
        msg = make_message("/help")
        await cmd_help(msg)
        msg.answer.assert_called_once()


# ---------------------------------------------------------------------------
# Profile handler
# ---------------------------------------------------------------------------

class TestProfileHandler:
    @pytest.mark.asyncio
    async def test_cmd_balance(self):
        from src.bot.handlers.profile import cmd_balance
        msg = make_message("/balance")
        user = make_user(balance_seconds=7200, free_uses_left=1)
        await cmd_balance(msg, user=user)
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "баланс" in text.lower() or "2" in text

    @pytest.mark.asyncio
    async def test_cmd_profile_no_subscription(self):
        from src.bot.handlers.profile import cmd_profile
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/profile")
        user = make_user()
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.profile.get_user_transcriptions", return_value=[]):
            await cmd_profile(msg, user=user, session=session)

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_profile_with_active_subscription(self):
        from src.bot.handlers.profile import cmd_profile
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/profile")
        user = make_user()

        sub = Subscription(
            id=1,
            user_id=123,
            plan="pro",
            status="active",
            seconds_limit=-1,
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        user.subscriptions = [sub]
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.profile.get_user_transcriptions", return_value=[]):
            await cmd_profile(msg, user=user, session=session)

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_history_empty(self):
        from src.bot.handlers.profile import cmd_history
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/history")
        user = make_user()
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.profile.get_user_transcriptions", return_value=[]):
            await cmd_history(msg, user=user, session=session)

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_history_with_items(self):
        from src.bot.handlers.profile import cmd_history
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/history")
        user = make_user()
        session = AsyncMock(spec=AsyncSession)

        t1 = Transcription(
            id="abc",
            user_id=123,
            status="done",
            duration_seconds=120,
            created_at=datetime.utcnow(),
        )
        t2 = Transcription(
            id="def",
            user_id=123,
            status="failed",
            duration_seconds=None,
            created_at=datetime.utcnow(),
        )

        with patch("src.bot.handlers.profile.get_user_transcriptions", return_value=[t1, t2]):
            await cmd_history(msg, user=user, session=session)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "✅" in text or "❌" in text


# ---------------------------------------------------------------------------
# Admin handler
# ---------------------------------------------------------------------------

class TestAdminHandler:
    def test_is_admin_by_flag(self):
        from src.bot.handlers.admin import is_admin
        user = make_user(is_admin=True)
        assert is_admin(user) is True

    def test_is_admin_in_list(self):
        from src.bot.handlers.admin import is_admin
        user = make_user(user_id=999)
        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = [999]
            assert is_admin(user) is True

    def test_is_not_admin(self):
        from src.bot.handlers.admin import is_admin
        user = make_user(is_admin=False)
        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = []
            assert is_admin(user) is False

    @pytest.mark.asyncio
    async def test_cmd_admin_not_admin(self):
        from src.bot.handlers.admin import cmd_admin
        from aiogram.fsm.context import FSMContext

        msg = make_message("/admin")
        user = make_user(is_admin=False)
        state = AsyncMock(spec=FSMContext)

        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = []
            await cmd_admin(msg, user=user, state=state)

        msg.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_cmd_admin_is_admin(self):
        from src.bot.handlers.admin import cmd_admin
        from aiogram.fsm.context import FSMContext

        msg = make_message("/admin")
        user = make_user(is_admin=True)
        state = AsyncMock(spec=FSMContext)

        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = []
            await cmd_admin(msg, user=user, state=state)

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_cmd_admin_balance_not_admin(self):
        from src.bot.handlers.admin import cmd_admin_balance
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/admin_balance 456 3600")
        user = make_user(is_admin=False)
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = []
            await cmd_admin_balance(msg, user=user, session=session)

        msg.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_cmd_admin_balance_wrong_args(self):
        from src.bot.handlers.admin import cmd_admin_balance
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/admin_balance")
        user = make_user(is_admin=True)
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = []
            await cmd_admin_balance(msg, user=user, session=session)

        msg.answer.assert_called_once()
        assert "Использование" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_admin_balance_invalid_args(self):
        from src.bot.handlers.admin import cmd_admin_balance
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/admin_balance abc xyz")
        user = make_user(is_admin=True)
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = []
            await cmd_admin_balance(msg, user=user, session=session)

        assert "Неверные" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_admin_balance_user_not_found(self):
        from src.bot.handlers.admin import cmd_admin_balance
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/admin_balance 456 3600")
        user = make_user(is_admin=True)
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = []
            with patch("src.bot.handlers.admin.get_user", return_value=None):
                await cmd_admin_balance(msg, user=user, session=session)

        assert "не найден" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_admin_balance_success(self):
        from src.bot.handlers.admin import cmd_admin_balance
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/admin_balance 456 3600")
        user = make_user(is_admin=True)
        target = make_user(user_id=456)
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = []
            with patch("src.bot.handlers.admin.get_user", return_value=target):
                with patch("src.bot.handlers.admin.add_balance", return_value=target):
                    await cmd_admin_balance(msg, user=user, session=session)

        assert "Добавлено" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_admin_ban_not_admin(self):
        from src.bot.handlers.admin import cmd_admin_ban
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/admin_ban 456")
        user = make_user(is_admin=False)
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = []
            await cmd_admin_ban(msg, user=user, session=session)

        msg.answer.assert_not_called()

    @pytest.mark.asyncio
    async def test_cmd_admin_ban_success(self):
        from src.bot.handlers.admin import cmd_admin_ban
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/admin_ban 456")
        user = make_user(is_admin=True)
        target = make_user(user_id=456)
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()

        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = []
            with patch("src.bot.handlers.admin.get_user", return_value=target):
                await cmd_admin_ban(msg, user=user, session=session)

        assert target.is_banned is True
        assert "заблокирован" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_admin_ban_wrong_args(self):
        from src.bot.handlers.admin import cmd_admin_ban
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/admin_ban")
        user = make_user(is_admin=True)
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = []
            await cmd_admin_ban(msg, user=user, session=session)

        assert "Использование" in msg.answer.call_args[0][0]

    @pytest.mark.asyncio
    async def test_cmd_admin_ban_invalid_id(self):
        from src.bot.handlers.admin import cmd_admin_ban
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("/admin_ban notanumber")
        user = make_user(is_admin=True)
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.admin.settings") as mock_settings:
            mock_settings.admin_ids_list = []
            await cmd_admin_ban(msg, user=user, session=session)

        assert "Неверный" in msg.answer.call_args[0][0]


# ---------------------------------------------------------------------------
# Promo handler
# ---------------------------------------------------------------------------

class TestPromoHandler:
    @pytest.mark.asyncio
    async def test_cmd_promo_sets_state(self):
        from src.bot.handlers.promo import cmd_promo
        from aiogram.fsm.context import FSMContext

        msg = make_message("/promo")
        state = AsyncMock(spec=FSMContext)

        await cmd_promo(msg, state=state)

        msg.answer.assert_called_once()
        state.set_state.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_promo_invalid_code(self):
        from src.bot.handlers.promo import process_promo
        from aiogram.fsm.context import FSMContext
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("INVALIDCODE")
        user = make_user()
        state = AsyncMock(spec=FSMContext)
        session = AsyncMock(spec=AsyncSession)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        await process_promo(msg, user=user, session=session, state=state)

        msg.answer.assert_called_once()
        state.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_promo_expired_code(self):
        from src.bot.handlers.promo import process_promo
        from aiogram.fsm.context import FSMContext
        from sqlalchemy.ext.asyncio import AsyncSession
        from src.db.models.promo_code import PromoCode

        msg = make_message("EXPIRED")
        user = make_user()
        state = AsyncMock(spec=FSMContext)
        session = AsyncMock(spec=AsyncSession)

        promo = PromoCode(
            id=1,
            code="EXPIRED",
            type="free_seconds",
            value=3600,
            is_active=True,
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = promo
        session.execute = AsyncMock(return_value=mock_result)

        await process_promo(msg, user=user, session=session, state=state)

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_promo_already_used(self):
        from src.bot.handlers.promo import process_promo
        from aiogram.fsm.context import FSMContext
        from sqlalchemy.ext.asyncio import AsyncSession
        from src.db.models.promo_code import PromoCode, PromoCodeUse

        msg = make_message("USED")
        user = make_user()
        state = AsyncMock(spec=FSMContext)
        session = AsyncMock(spec=AsyncSession)

        promo = PromoCode(
            id=1,
            code="USED",
            type="free_seconds",
            value=3600,
            is_active=True,
            expires_at=None,
            max_uses=None,
            used_count=0,
        )

        use_record = PromoCodeUse(promo_code_id=1, user_id=123)

        results = [
            MagicMock(**{"scalar_one_or_none.return_value": promo}),
            MagicMock(**{"scalar_one_or_none.return_value": use_record}),
        ]
        session.execute = AsyncMock(side_effect=results)

        await process_promo(msg, user=user, session=session, state=state)

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_promo_success(self):
        from src.bot.handlers.promo import process_promo
        from aiogram.fsm.context import FSMContext
        from sqlalchemy.ext.asyncio import AsyncSession
        from src.db.models.promo_code import PromoCode

        msg = make_message("VALID99")
        user = make_user()
        state = AsyncMock(spec=FSMContext)
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()

        promo = PromoCode(
            id=1,
            code="VALID99",
            type="free_seconds",
            value=7200,
            is_active=True,
            expires_at=None,
            max_uses=None,
            used_count=0,
        )

        results = [
            MagicMock(**{"scalar_one_or_none.return_value": promo}),
            MagicMock(**{"scalar_one_or_none.return_value": None}),  # not yet used
        ]
        session.execute = AsyncMock(side_effect=results)

        with patch("src.bot.handlers.promo.add_balance", return_value=user):
            await process_promo(msg, user=user, session=session, state=state)

        msg.answer.assert_called_once()
        assert "2 ч" in msg.answer.call_args[0][0] or "ч" in msg.answer.call_args[0][0]


# ---------------------------------------------------------------------------
# Referral handler
# ---------------------------------------------------------------------------

class TestReferralHandler:
    @pytest.mark.asyncio
    async def test_cmd_referral(self):
        from sqlalchemy.ext.asyncio import AsyncSession

        from src.bot.handlers.referral import cmd_referral

        msg = make_message("/referral")
        user = make_user()
        session = AsyncMock(spec=AsyncSession)
        session.scalar = AsyncMock(side_effect=[5, 150.0])

        await cmd_referral(msg, user=user, session=session)

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "ref_123" in text or "t.me" in text


# ---------------------------------------------------------------------------
# Links handler
# ---------------------------------------------------------------------------

class TestLinksHandler:
    def test_detect_source_type_youtube(self):
        from src.bot.handlers.links import _detect_source_type
        assert _detect_source_type("https://www.youtube.com/watch?v=abc") == "youtube"
        assert _detect_source_type("https://youtu.be/abc") == "youtube"

    def test_detect_source_type_rutube(self):
        from src.bot.handlers.links import _detect_source_type
        assert _detect_source_type("https://rutube.ru/video/abc") == "rutube"

    def test_detect_source_type_gdrive(self):
        from src.bot.handlers.links import _detect_source_type
        assert _detect_source_type("https://drive.google.com/file/d/abc") == "gdrive"

    def test_detect_source_type_yadisk(self):
        from src.bot.handlers.links import _detect_source_type
        assert _detect_source_type("https://disk.yandex.ru/i/abc") == "yadisk"
        assert _detect_source_type("https://yadi.sk/abc") == "yadisk"

    def test_detect_source_type_vk(self):
        from src.bot.handlers.links import _detect_source_type
        assert _detect_source_type("https://vk.com/video123") == "vk"

    def test_detect_source_type_ok(self):
        from src.bot.handlers.links import _detect_source_type
        assert _detect_source_type("https://ok.ru/video/123") == "ok"

    def test_detect_source_type_unknown_defaults_youtube(self):
        from src.bot.handlers.links import _detect_source_type
        assert _detect_source_type("https://example.com/video") == "youtube"

    @pytest.mark.asyncio
    async def test_handle_url_unsupported(self):
        from src.bot.handlers.links import handle_url
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("https://invalid.xyz/video")
        user = make_user()
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.links.is_allowed_url", return_value=False):
            await handle_url(msg, user=user, session=session)

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_url_insufficient_balance(self):
        from src.bot.handlers.links import handle_url
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message("https://youtube.com/watch?v=abc")
        user = make_user(balance_seconds=0, free_uses_left=0)
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.links.is_allowed_url", return_value=True):
            with patch(
                "src.bot.handlers.links.check_can_transcribe",
                return_value=(False, "Недостаточно баланса"),
            ):
                await handle_url(msg, user=user, session=session)

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_url_success(self):
        from src.bot.handlers.links import handle_url
        from sqlalchemy.ext.asyncio import AsyncSession
        import sys

        msg = make_message("https://youtube.com/watch?v=abc")
        user = make_user(free_uses_left=1)
        session = AsyncMock(spec=AsyncSession)

        transcription = Transcription(id="t1", user_id=123, status="pending")
        mock_task = MagicMock(id="celery-task-1")
        mock_trans_module = MagicMock()
        mock_trans_module.transcribe_task.delay.return_value = mock_task

        with patch("src.bot.handlers.links.is_allowed_url", return_value=True):
            with patch(
                "src.bot.handlers.links.check_can_transcribe",
                return_value=(True, ""),
            ):
                with patch(
                    "src.bot.handlers.links.create_transcription",
                    return_value=transcription,
                ):
                    with patch(
                        "src.bot.handlers.links.decrement_free_uses",
                        return_value=None,
                    ):
                        with patch.dict(
                            sys.modules,
                            {"src.worker.tasks.transcription": mock_trans_module},
                        ):
                            await handle_url(msg, user=user, session=session)

        msg.answer.assert_called_once()


# ---------------------------------------------------------------------------
# Media handler
# ---------------------------------------------------------------------------

class TestMediaHandler:
    @pytest.mark.asyncio
    async def test_handle_media_file_too_large(self):
        from src.bot.handlers.media import _handle_media
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message()
        user = make_user()
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.media.validate_file_size", return_value=False):
            await _handle_media(
                msg, user, session,
                source_type="audio",
                file_id="f1",
                file_unique_id="u1",
                file_size=999_999_999,
                mime_type="audio/mp3",
            )

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_media_unsupported_mime(self):
        from src.bot.handlers.media import _handle_media
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message()
        user = make_user()
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.media.validate_file_size", return_value=True):
            with patch("src.bot.handlers.media.validate_mime_type", return_value=False):
                await _handle_media(
                    msg, user, session,
                    source_type="audio",
                    file_id="f1",
                    file_unique_id="u1",
                    file_size=1000,
                    mime_type="application/exe",
                )

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_media_cached_result(self):
        from src.bot.handlers.media import _handle_media
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message()
        user = make_user()
        session = AsyncMock(spec=AsyncSession)

        cached = Transcription(
            id="cached1",
            user_id=123,
            status="done",
            result_text="Cached transcription text",
        )

        with patch("src.bot.handlers.media.validate_file_size", return_value=True):
            with patch("src.bot.handlers.media.validate_mime_type", return_value=True):
                with patch(
                    "src.bot.handlers.media.get_cached_transcription",
                    return_value=cached,
                ):
                    await _handle_media(
                        msg, user, session,
                        source_type="audio",
                        file_id="f1",
                        file_unique_id="u1",
                        file_size=1000,
                        mime_type="audio/mp3",
                    )

        msg.answer.assert_called_once()
        assert "кэш" in msg.answer.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_handle_media_insufficient_balance(self):
        from src.bot.handlers.media import _handle_media
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message()
        user = make_user(balance_seconds=0, free_uses_left=0)
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.media.validate_file_size", return_value=True):
            with patch("src.bot.handlers.media.validate_mime_type", return_value=True):
                with patch(
                    "src.bot.handlers.media.get_cached_transcription",
                    return_value=None,
                ):
                    with patch(
                        "src.bot.handlers.media.check_can_transcribe",
                        return_value=(False, "Нет баланса"),
                    ):
                        await _handle_media(
                            msg, user, session,
                            source_type="audio",
                            file_id="f1",
                            file_unique_id="u1",
                            file_size=1000,
                            mime_type="audio/mp3",
                        )

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_media_success(self):
        from src.bot.handlers.media import _handle_media
        from sqlalchemy.ext.asyncio import AsyncSession
        import sys

        msg = make_message()
        user = make_user(free_uses_left=1)
        session = AsyncMock(spec=AsyncSession)
        session.execute = AsyncMock()
        session.commit = AsyncMock()

        transcription = Transcription(id="t1", user_id=123, status="pending")
        mock_task = MagicMock(id="celery-task-1")
        mock_trans_module = MagicMock()
        mock_trans_module.transcribe_task.delay.return_value = mock_task

        with patch("src.bot.handlers.media.validate_file_size", return_value=True):
            with patch("src.bot.handlers.media.validate_mime_type", return_value=True):
                with patch(
                    "src.bot.handlers.media.get_cached_transcription", return_value=None
                ):
                    with patch(
                        "src.bot.handlers.media.check_can_transcribe",
                        return_value=(True, ""),
                    ):
                        with patch(
                            "src.bot.handlers.media.create_transcription",
                            return_value=transcription,
                        ):
                            with patch(
                                "src.bot.handlers.media.decrement_free_uses",
                                return_value=None,
                            ):
                                with patch.dict(
                                    sys.modules,
                                    {"src.worker.tasks.transcription": mock_trans_module},
                                ):
                                    await _handle_media(
                                        msg, user, session,
                                        source_type="audio",
                                        file_id="f1",
                                        file_unique_id="u1",
                                        file_size=1000,
                                        mime_type="audio/mp3",
                                    )

        msg.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_document_unsupported_mime(self):
        from src.bot.handlers.media import handle_document
        from sqlalchemy.ext.asyncio import AsyncSession

        msg = make_message()
        doc = MagicMock()
        doc.mime_type = "application/zip"
        doc.file_id = "f1"
        doc.file_unique_id = "u1"
        doc.file_size = 1000
        doc.file_name = "file.zip"
        msg.document = doc
        user = make_user()
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.media.validate_mime_type", return_value=False):
            await handle_document(msg, user=user, session=session)

        msg.answer.assert_called_once()


# ---------------------------------------------------------------------------
# Callbacks handler
# ---------------------------------------------------------------------------

class TestCallbacksHandler:
    @pytest.mark.asyncio
    async def test_cb_summary_not_found(self):
        from src.bot.handlers.callbacks import cb_summary
        from sqlalchemy.ext.asyncio import AsyncSession

        cb = make_callback("summary:nonexistent")
        user = make_user()
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.callbacks.get_transcription", return_value=None):
            await cb_summary(cb, user=user, session=session)

        cb.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_cb_summary_wrong_user(self):
        from src.bot.handlers.callbacks import cb_summary
        from sqlalchemy.ext.asyncio import AsyncSession

        cb = make_callback("summary:t1")
        user = make_user(user_id=123)
        session = AsyncMock(spec=AsyncSession)

        other_transcription = Transcription(id="t1", user_id=999, status="done")

        with patch(
            "src.bot.handlers.callbacks.get_transcription",
            return_value=other_transcription,
        ):
            await cb_summary(cb, user=user, session=session)

        cb.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_cb_summary_already_has_summary(self):
        from src.bot.handlers.callbacks import cb_summary
        from sqlalchemy.ext.asyncio import AsyncSession

        cb = make_callback("summary:t1")
        user = make_user(user_id=123)
        session = AsyncMock(spec=AsyncSession)

        transcription = Transcription(
            id="t1",
            user_id=123,
            status="done",
            summary_text="Already generated summary.",
        )

        with patch(
            "src.bot.handlers.callbacks.get_transcription",
            return_value=transcription,
        ):
            await cb_summary(cb, user=user, session=session)

        cb.message.answer.assert_called_once()
        cb.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_cb_summary_dispatch_to_worker(self):
        from src.bot.handlers.callbacks import cb_summary
        from sqlalchemy.ext.asyncio import AsyncSession
        import sys

        cb = make_callback("summary:t1")
        user = make_user(user_id=123)
        session = AsyncMock(spec=AsyncSession)

        transcription = Transcription(
            id="t1",
            user_id=123,
            status="done",
            result_text="Some text",
            summary_text=None,
        )

        mock_summary_module = MagicMock()

        with patch(
            "src.bot.handlers.callbacks.get_transcription",
            return_value=transcription,
        ):
            with patch.dict(
                sys.modules, {"src.worker.tasks.summary": mock_summary_module}
            ):
                await cb_summary(cb, user=user, session=session)

        mock_summary_module.summary_task.delay.assert_called_once()
        cb.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_cb_docx_not_found(self):
        from src.bot.handlers.callbacks import cb_docx
        from sqlalchemy.ext.asyncio import AsyncSession

        cb = make_callback("docx:t1")
        user = make_user()
        session = AsyncMock(spec=AsyncSession)

        with patch("src.bot.handlers.callbacks.get_transcription", return_value=None):
            await cb_docx(cb, user=user, session=session)

        cb.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_cb_docx_success(self):
        from src.bot.handlers.callbacks import cb_docx
        from sqlalchemy.ext.asyncio import AsyncSession
        import sys

        cb = make_callback("docx:t1")
        user = make_user(user_id=123)
        session = AsyncMock(spec=AsyncSession)

        transcription = Transcription(
            id="t1",
            user_id=123,
            status="done",
            result_text="Full text here",
        )
        mock_summary_module = MagicMock()

        with patch(
            "src.bot.handlers.callbacks.get_transcription",
            return_value=transcription,
        ):
            with patch.dict(
                sys.modules, {"src.worker.tasks.summary": mock_summary_module}
            ):
                await cb_docx(cb, user=user, session=session)

        mock_summary_module.docx_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_cb_language_sets_redis(self):
        import sys

        cb = make_callback("lang:ru")
        user = make_user()

        mock_redis_client = AsyncMock()  # all attrs auto-async
        redis_mod = sys.modules.get("redis", MagicMock())
        redis_mod.asyncio.from_url.return_value = mock_redis_client

        from src.bot.handlers.callbacks import cb_language
        with patch("src.bot.handlers.callbacks.settings") as mock_settings:
            mock_settings.redis_cache_url = "redis://localhost/1"
            await cb_language(cb, user=user)

        mock_redis_client.set.assert_called_once()
        cb.message.edit_text.assert_called_once()
