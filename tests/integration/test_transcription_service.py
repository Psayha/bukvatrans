import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock


class TestTranscribeChunk:
    @pytest.mark.asyncio
    async def test_successful_transcription(self, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"text": "Тестовый текст"}

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            from src.services.transcription import transcribe_chunk
            result = await transcribe_chunk(audio_file, language="ru", api_key="test-key")

        assert result == "Тестовый текст"

    @pytest.mark.asyncio
    async def test_retry_on_http_error(self, tmp_path):
        """Should retry on HTTPStatusError."""
        import httpx

        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio data")

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.HTTPStatusError(
                    "Rate limited",
                    request=MagicMock(),
                    response=MagicMock(status_code=429),
                )
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json.return_value = {"text": "Успешно"}
            return mock_resp

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = mock_post
            mock_client_cls.return_value = mock_client

            from src.services.transcription import transcribe_chunk
            result = await transcribe_chunk(audio_file, language="ru", api_key="test-key")

        assert result == "Успешно"
        assert call_count == 3


class TestTranscribeAudio:
    @pytest.mark.asyncio
    async def test_small_file_no_chunking(self, tmp_path):
        """Small file should be transcribed as single chunk."""
        audio_file = tmp_path / "small.mp3"
        audio_file.write_bytes(b"x" * 1000)  # very small

        # needs_chunking is imported inside transcribe_audio from audio_processor
        with patch("src.services.audio_processor.needs_chunking", return_value=False):
            with patch("src.services.transcription.transcribe_chunk", new_callable=AsyncMock) as mock_chunk:
                mock_chunk.return_value = "Полный текст"
                from src.services.transcription import transcribe_audio
                text, segments = await transcribe_audio(audio_file, language="ru", api_key="test")

        assert text == "Полный текст"
        assert segments == []
        mock_chunk.assert_called_once()

    @pytest.mark.asyncio
    async def test_large_file_uses_chunking(self, tmp_path):
        """Large file should be split and merged."""
        audio_file = tmp_path / "large.mp3"
        audio_file.write_bytes(b"x" * (26 * 1024 * 1024))  # 26 MB

        chunk1 = tmp_path / "chunk_0000.mp3"
        chunk2 = tmp_path / "chunk_0001.mp3"
        chunk1.write_bytes(b"chunk1")
        chunk2.write_bytes(b"chunk2")

        with patch("src.services.audio_processor.needs_chunking", return_value=True):
            with patch("src.services.audio_processor.split_audio", new_callable=AsyncMock) as mock_split:
                mock_split.return_value = [chunk1, chunk2]
                with patch("src.services.transcription.transcribe_chunk", new_callable=AsyncMock) as mock_chunk:
                    mock_chunk.side_effect = ["Первая часть.", "Вторая часть."]
                    from src.services.transcription import transcribe_audio
                    text, _ = await transcribe_audio(audio_file, api_key="test")

        assert "Первая часть." in text
        assert "Вторая часть." in text
        assert mock_chunk.call_count == 2
