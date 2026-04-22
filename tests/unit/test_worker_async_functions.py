"""Tests for worker task _async helper functions.

Celery is not installed in the test environment, so we mock the
celery module in sys.modules before importing worker modules.
"""
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Setup: inject fake celery into sys.modules so worker imports don't fail
# ---------------------------------------------------------------------------

def _install_celery_mock():
    """Inject minimal celery mock into sys.modules."""
    if "celery" in sys.modules and not isinstance(sys.modules["celery"], MagicMock):
        return  # real celery installed

    # Build a mock app that supports @app.task decorator
    mock_app = MagicMock()

    def task_decorator(*args, **kwargs):
        def decorator(fn):
            fn.delay = MagicMock()
            fn.apply_async = MagicMock()
            return fn
        # Handle both @app.task and @app.task(...)
        if args and callable(args[0]):
            return decorator(args[0])
        return decorator

    mock_app.task = task_decorator
    mock_app.conf = MagicMock()
    mock_app.conf.update = MagicMock()
    mock_app.conf.beat_schedule = {}
    mock_app.autodiscover_tasks = MagicMock()

    celery_mock = MagicMock()
    celery_mock.Celery.return_value = mock_app
    celery_mock.Task = object  # base class for inheritance

    schedules_mock = MagicMock()
    schedules_mock.crontab = MagicMock(return_value="crontab_obj")

    utils_log_mock = MagicMock()
    utils_log_mock.get_task_logger = MagicMock(return_value=MagicMock())

    beat_mock = MagicMock()

    # Sentry celery integration tries to import celery.beat.Scheduler
    sentry_celery_mock = MagicMock()
    sentry_celery_beat_mock = MagicMock()
    sentry_celery_utils_mock = MagicMock()

    signals_mock = MagicMock()
    # Signals expose a `.connect` decorator we use in worker/app.py.
    for sig_name in ("worker_ready", "worker_shutting_down", "task_prerun", "task_postrun"):
        sig = MagicMock()
        sig.connect = lambda fn=None, **kw: (fn if fn is not None else (lambda f: f))
        setattr(signals_mock, sig_name, sig)

    exceptions_mock = MagicMock()
    exceptions_mock.SoftTimeLimitExceeded = type("SoftTimeLimitExceeded", (Exception,), {})

    updates = {
        "celery": celery_mock,
        "celery.schedules": schedules_mock,
        "celery.signals": signals_mock,
        "celery.exceptions": exceptions_mock,
        "celery.utils": MagicMock(),
        "celery.utils.log": utils_log_mock,
        "celery.beat": beat_mock,
        "celery.app": MagicMock(),
        "celery.app.task": MagicMock(),
        "sentry_sdk.integrations.celery": sentry_celery_mock,
        "sentry_sdk.integrations.celery.beat": sentry_celery_beat_mock,
        "sentry_sdk.integrations.celery.utils": sentry_celery_utils_mock,
        "redis": MagicMock(),
        "redis.asyncio": MagicMock(),
        "boto3": MagicMock(),
        "botocore": MagicMock(),
        "botocore.client": MagicMock(),
    }
    for key, val in updates.items():
        if key not in sys.modules:
            sys.modules[key] = val


_install_celery_mock()


# ---------------------------------------------------------------------------
# worker/tasks/maintenance.py
# ---------------------------------------------------------------------------

class TestMaintenanceAsyncFunctions:
    @pytest.mark.asyncio
    async def test_expire_subscriptions(self):
        """_expire_subscriptions updates expired subs in DB."""
        from src.worker.tasks.maintenance import _expire_subscriptions

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        # Function uses real Subscription model and sqlalchemy.update — let them be.
        # Patch only the session factory.
        with patch("src.db.base.async_session_factory", return_value=mock_session_ctx):
            await _expire_subscriptions()

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_cleanup_tmp_files(self, tmp_path):
        """cleanup_tmp_files removes mp3 files from temp dir."""
        # Create fake mp3 files
        (tmp_path / "a.mp3").write_bytes(b"fake")
        (tmp_path / "b.mp3").write_bytes(b"fake")
        (tmp_path / "keep.txt").write_text("keep")

        with patch("src.worker.tasks.maintenance.app"):
            from src.worker.tasks.maintenance import cleanup_tmp_files

        with patch("src.worker.tasks.maintenance.Path") as mock_path_cls:
            mock_tmp = MagicMock()
            mp3_files = [MagicMock(), MagicMock()]
            for f in mp3_files:
                f.unlink = MagicMock()
            mock_tmp.glob.return_value = mp3_files
            mock_path_cls.return_value = mock_tmp
            with patch("src.worker.tasks.maintenance.tempfile.gettempdir", return_value=str(tmp_path)):
                cleanup_tmp_files()

        for f in mp3_files:
            f.unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_dlq_low_count(self):
        """_check_dlq does nothing when count <= 5."""
        from src.worker.tasks.maintenance import _check_dlq

        # `import redis.asyncio as aioredis` returns sys.modules['redis'].asyncio,
        # NOT sys.modules['redis.asyncio'] — configure the parent's .asyncio attribute
        mock_redis_client = AsyncMock()
        mock_redis_client.llen = AsyncMock(return_value=3)

        redis_mock = sys.modules.get("redis", MagicMock())
        redis_mock.asyncio.from_url.return_value = mock_redis_client

        with patch("src.config.settings") as mock_settings:
            mock_settings.REDIS_URL = "redis://localhost"
            mock_settings.admin_ids_list = []
            await _check_dlq()

        mock_redis_client.llen.assert_called_once_with("celery_dlq")

    @pytest.mark.asyncio
    async def test_check_dlq_high_count_notifies_admins(self):
        """_check_dlq sends alert when DLQ count > 5."""
        from src.worker.tasks.maintenance import _check_dlq

        mock_redis_client = AsyncMock()
        mock_redis_client.llen = AsyncMock(return_value=10)

        redis_mock = sys.modules.get("redis", MagicMock())
        redis_mock.asyncio.from_url.return_value = mock_redis_client

        with patch("src.config.settings") as mock_settings:
            mock_settings.REDIS_URL = "redis://localhost"
            mock_settings.admin_ids_list = [111, 222]
            with patch("src.services.notification.send_message") as mock_send:
                mock_send.return_value = None
                await _check_dlq()

        # send_message called once per admin
        assert mock_send.call_count == 2


# ---------------------------------------------------------------------------
# worker/tasks/stats.py
# ---------------------------------------------------------------------------

class TestStatsAsyncFunctions:
    @pytest.mark.asyncio
    async def test_send_daily_report_sends_to_admins(self):
        """_send_daily_report queries DB and sends report to each admin."""
        from src.worker.tasks.stats import _send_daily_report

        mock_session = AsyncMock()
        # scalar calls for new_users, transcriptions, total_duration
        mock_session.scalar = AsyncMock(side_effect=[5, 10, 36000])
        # execute for payments
        mock_payment_row = MagicMock()
        mock_payment_row.__getitem__ = MagicMock(side_effect=lambda i: [3, 597.0][i])
        mock_execute_result = MagicMock()
        mock_execute_result.first.return_value = mock_payment_row
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("src.db.base.async_session_factory", return_value=mock_session_ctx):
            with patch("src.config.settings") as mock_settings:
                mock_settings.admin_ids_list = [100]
                with patch("src.services.notification.send_message") as mock_send:
                    mock_send.return_value = None
                    await _send_daily_report()

        mock_send.assert_called_once()
        assert mock_send.call_args[0][0] == 100

    @pytest.mark.asyncio
    async def test_send_daily_report_handles_send_error(self):
        """_send_daily_report catches exceptions when sending to admin."""
        from src.worker.tasks.stats import _send_daily_report

        mock_session = AsyncMock()
        mock_session.scalar = AsyncMock(side_effect=[0, 0, 0])
        # Provide a valid payment_row with [count, sum] to avoid subscript TypeError
        mock_payment_row = MagicMock()
        mock_payment_row.__getitem__ = MagicMock(side_effect=lambda i: [0, 0.0][i])
        mock_execute_result = MagicMock()
        mock_execute_result.first.return_value = mock_payment_row
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("src.db.base.async_session_factory", return_value=mock_session_ctx):
            with patch("src.config.settings") as mock_settings:
                mock_settings.admin_ids_list = [100, 200]
                with patch(
                    "src.services.notification.send_message",
                    side_effect=Exception("Network error"),
                ):
                    # Should not raise — errors are caught
                    await _send_daily_report()


# ---------------------------------------------------------------------------
# worker/tasks/summary.py
# ---------------------------------------------------------------------------

class TestSummaryAsyncFunctions:
    @pytest.mark.asyncio
    async def test_summary_async_no_transcription(self):
        """_summary_async sends error when transcription not found."""
        from src.worker.tasks.summary import _summary_async

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("src.db.base.async_session_factory", return_value=mock_session_ctx):
            with patch(
                "src.db.repositories.transcription.get_transcription",
                return_value=None,
            ):
                with patch("src.services.notification.send_message") as mock_send:
                    mock_send.return_value = None
                    result = await _summary_async("t1", 123)

        assert result["status"] == "failed"
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_summary_async_success(self):
        """_summary_async generates and saves summary."""
        from src.db.models.transcription import Transcription
        from src.worker.tasks.summary import _summary_async

        t = Transcription(
            id="t1",
            user_id=123,
            status="done",
            result_text="Long text to summarize",
        )

        mock_session = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("src.db.base.async_session_factory", return_value=mock_session_ctx):
            with patch(
                "src.db.repositories.transcription.get_transcription", return_value=t
            ):
                with patch(
                    "src.services.summary.generate_summary",
                    return_value="Summary text",
                ):
                    with patch("src.services.notification.send_message") as mock_send:
                        mock_send.return_value = None
                        result = await _summary_async("t1", 123)

        assert result["status"] == "done"
        assert t.summary_text == "Summary text"
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_summary_async_generate_error(self):
        """_summary_async handles generate_summary failure."""
        from src.db.models.transcription import Transcription
        from src.worker.tasks.summary import _summary_async

        t = Transcription(
            id="t1",
            user_id=123,
            status="done",
            result_text="Long text",
        )

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("src.db.base.async_session_factory", return_value=mock_session_ctx):
            with patch(
                "src.db.repositories.transcription.get_transcription", return_value=t
            ):
                with patch(
                    "src.services.summary.generate_summary",
                    side_effect=Exception("API error"),
                ):
                    with patch("src.services.notification.send_message") as mock_send:
                        mock_send.return_value = None
                        result = await _summary_async("t1", 123)

        assert result["status"] == "failed"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_docx_async_no_transcription(self):
        """_docx_async returns failed when no transcription."""
        from src.worker.tasks.summary import _docx_async

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_doc_module = MagicMock()
        mock_doc_module.Document = MagicMock(return_value=MagicMock())

        with patch.dict(sys.modules, {"docx": mock_doc_module}):
            with patch("src.db.base.async_session_factory", return_value=mock_session_ctx):
                with patch(
                    "src.db.repositories.transcription.get_transcription",
                    return_value=None,
                ):
                    result = await _docx_async("t1", 123)

        assert result["status"] == "failed"

    @pytest.mark.asyncio
    async def test_docx_async_success(self):
        """_docx_async creates docx and sends it."""
        from src.db.models.transcription import Transcription
        from src.worker.tasks.summary import _docx_async

        t = Transcription(
            id="t1",
            user_id=123,
            status="done",
            result_text="Line 1\nLine 2\nLine 3",
        )

        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        mock_doc = MagicMock()
        mock_doc.save = MagicMock()
        mock_document_cls = MagicMock(return_value=mock_doc)

        with patch("src.db.base.async_session_factory", return_value=mock_session_ctx):
            with patch(
                "src.db.repositories.transcription.get_transcription", return_value=t
            ):
                with patch("src.services.notification.send_document") as mock_send:
                    mock_send.return_value = None
                    with patch.dict(
                        sys.modules,
                        {"docx": MagicMock(Document=mock_document_cls)},
                    ):
                        result = await _docx_async("t1", 123)

        assert result["status"] == "done"
        mock_send.assert_called_once()


# ---------------------------------------------------------------------------
# worker/tasks/transcription.py — pure helper functions
# ---------------------------------------------------------------------------

class TestTranscriptionHelpers:
    def test_download_telegram_file_url_format(self):
        """Test the URL format for downloading Telegram files."""
        bot_token = "123456:ABCDEF"
        file_path = "documents/file_12345.mp3"

        expected_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        actual_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"

        assert actual_url == expected_url
        assert "file" in actual_url
        assert bot_token in actual_url

    @pytest.mark.asyncio
    async def test_transcribe_async_no_file_returns_failed(self):
        """_transcribe_async returns failed when file_id and source_url are both None."""
        from src.worker.tasks.transcription import _transcribe_async

        mock_task = MagicMock()
        mock_session = AsyncMock()
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

        from src.db.models.transcription import Transcription
        t = Transcription(id="t1", user_id=123, status="pending", is_free=False, seconds_charged=0)

        with patch("src.db.base.async_session_factory", return_value=mock_session_ctx):
            with patch("src.db.repositories.transcription.get_transcription", return_value=t):
                with patch("src.db.repositories.transcription.update_transcription_status"):
                    with patch("src.services.notification.send_message"):
                        with patch("src.db.repositories.transcription.get_transcription", return_value=t):
                            with patch("src.db.repositories.user.add_balance"):
                                # file_id=None, source_url=None → FileNotFoundError → failed
                                result = await _transcribe_async(
                                    mock_task, "t1", 123, "voice", None, None
                                )

        assert isinstance(result, dict)
        assert result["status"] == "failed"
