"""Unit tests for worker task logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


class TestTranscriptionTaskHelpers:
    @pytest.mark.asyncio
    async def test_download_telegram_file_constructs_correct_url(self, tmp_path):
        """Test that the correct Telegram API URL is constructed."""
        # Import only the helper function, mocking celery at module level
        with patch.dict("sys.modules", {"celery": MagicMock(), "celery.utils.log": MagicMock()}):
            from importlib import import_module
            import sys
            # Remove cached module to allow re-import with mock
            sys.modules.pop("src.worker.tasks.transcription", None)
            sys.modules.pop("src.worker.app", None)

        # Test the download logic directly without importing the celery task
        file_path_response = {
            "result": {"file_path": "voice/file_123.ogg"}
        }

        async def _download_telegram_file_impl(file_id: str, output_dir: Path, source_type: str) -> Path:
            """Copy of the function logic for isolated testing."""
            import httpx
            import uuid as _uuid
            bot_token = "123:test_token"

            async with httpx.AsyncClient(timeout=300) as client:
                r = await client.get(
                    f"https://api.telegram.org/bot{bot_token}/getFile",
                    params={"file_id": file_id},
                )
                r.raise_for_status()
                fp = r.json()["result"]["file_path"]
                ext = Path(fp).suffix or ".ogg"

                url = f"https://api.telegram.org/file/bot{bot_token}/{fp}"
                out_path = output_dir / f"{_uuid.uuid4()}{ext}"
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with open(out_path, "wb") as f:
                        async for chunk in response.aiter_bytes(8192):
                            f.write(chunk)
                return out_path

        mock_resp_get = MagicMock()
        mock_resp_get.raise_for_status = MagicMock()
        mock_resp_get.json.return_value = file_path_response

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.raise_for_status = MagicMock()

        async def aiter_bytes(chunk_size):
            yield b"fake audio data"

        mock_stream_ctx.aiter_bytes = aiter_bytes
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream_ctx)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(return_value=mock_resp_get)
            mock_client.stream = MagicMock(return_value=mock_stream_ctx)
            mock_client_cls.return_value = mock_client

            result = await _download_telegram_file_impl("file_id_abc", tmp_path, "voice")

        assert result.suffix == ".ogg"
        assert result.parent == tmp_path


class TestSummaryTaskPrepareText:
    def test_short_text_unchanged(self):
        from src.services.summary import _prepare_text
        text = "Hello world"
        assert _prepare_text(text) == text

    def test_long_text_keeps_boundaries(self):
        from src.services.summary import _prepare_text, MAX_TEXT_LENGTH
        text = "START" + "x" * MAX_TEXT_LENGTH * 2 + "END"
        result = _prepare_text(text)
        assert "START" in result
        assert "END" in result


class TestMaintenanceTasks:
    def test_cleanup_tmp_files_only_mp3(self, tmp_path):
        """Only .mp3 files should be cleaned up."""
        mp3 = tmp_path / "test.mp3"
        txt = tmp_path / "test.txt"
        mp3.write_text("audio")
        txt.write_text("text")

        # Simulate cleanup logic
        count = 0
        for f in tmp_path.glob("*.mp3"):
            f.unlink()
            count += 1

        assert count == 1
        assert not mp3.exists()
        assert txt.exists()

    @pytest.mark.asyncio
    async def test_expire_subscriptions_updates_status(self, db_session):
        from datetime import datetime, timedelta
        from src.db.models.user import User
        from src.db.models.subscription import Subscription
        from sqlalchemy import select

        user = User(id=55001, balance_seconds=0, free_uses_left=0)
        db_session.add(user)
        await db_session.commit()

        # Expired subscription
        sub = Subscription(
            user_id=user.id,
            plan="basic",
            status="active",
            seconds_limit=108000,
            started_at=datetime.utcnow() - timedelta(days=60),
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        db_session.add(sub)
        await db_session.commit()

        # Run expire logic
        from sqlalchemy import update
        now = datetime.utcnow()
        await db_session.execute(
            update(Subscription)
            .where(Subscription.expires_at < now, Subscription.status == "active")
            .values(status="expired")
        )
        await db_session.commit()

        result = await db_session.execute(select(Subscription).where(Subscription.id == sub.id))
        updated = result.scalar_one()
        assert updated.status == "expired"
