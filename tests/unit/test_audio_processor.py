import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

from src.services.audio_processor import (
    split_audio,
    merge_transcriptions,
    needs_chunking,
    GROQ_MAX_FILE_BYTES,
    CHUNK_DURATION_SECONDS,
)


class TestSplitAudio:
    @pytest.mark.asyncio
    async def test_short_audio_one_chunk(self, tmp_path):
        """Audio < 10 min → 1 chunk."""
        with patch("src.services.audio_processor.get_audio_duration", return_value=300.0):
            with patch("asyncio.create_subprocess_exec") as mock_proc:
                mock_proc.return_value = AsyncMock(wait=AsyncMock(return_value=0))
                chunks = await split_audio(Path("/fake/audio.mp3"), tmp_path)
                assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_25_min_audio_splits_into_3(self, tmp_path):
        """Audio 25 min (1500s) → ceil(1500/600) = 3 chunks."""
        with patch("src.services.audio_processor.get_audio_duration", return_value=1500.0):
            with patch("asyncio.create_subprocess_exec") as mock_proc:
                mock_proc.return_value = AsyncMock(wait=AsyncMock(return_value=0))
                chunks = await split_audio(Path("/fake/audio.mp3"), tmp_path)
                assert len(chunks) == 3

    @pytest.mark.asyncio
    async def test_exactly_10_min_one_chunk(self, tmp_path):
        """Exactly 600s → 1 chunk."""
        with patch("src.services.audio_processor.get_audio_duration", return_value=600.0):
            with patch("asyncio.create_subprocess_exec") as mock_proc:
                mock_proc.return_value = AsyncMock(wait=AsyncMock(return_value=0))
                chunks = await split_audio(Path("/fake/audio.mp3"), tmp_path)
                assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_10_min_plus_1s_two_chunks(self, tmp_path):
        """601s → 2 chunks."""
        with patch("src.services.audio_processor.get_audio_duration", return_value=601.0):
            with patch("asyncio.create_subprocess_exec") as mock_proc:
                mock_proc.return_value = AsyncMock(wait=AsyncMock(return_value=0))
                chunks = await split_audio(Path("/fake/audio.mp3"), tmp_path)
                assert len(chunks) == 2

    @pytest.mark.asyncio
    async def test_chunk_names_are_sequential(self, tmp_path):
        """Chunk files are named chunk_0000.mp3, chunk_0001.mp3, etc."""
        with patch("src.services.audio_processor.get_audio_duration", return_value=1200.0):
            with patch("asyncio.create_subprocess_exec") as mock_proc:
                mock_proc.return_value = AsyncMock(wait=AsyncMock(return_value=0))
                chunks = await split_audio(Path("/fake/audio.mp3"), tmp_path)
                names = [c.name for c in chunks]
                assert names[0] == "chunk_0000.mp3"
                assert names[1] == "chunk_0001.mp3"


class TestMergeTranscriptions:
    def test_single_chunk(self):
        texts = ["Привет, это тест."]
        result = merge_transcriptions(texts)
        assert result == "Привет, это тест."

    def test_multiple_chunks_merged(self):
        texts = ["Первая часть текста.", "Вторая часть текста."]
        result = merge_transcriptions(texts)
        assert "Первая часть" in result
        assert "Вторая часть" in result

    def test_empty_chunks_skipped(self):
        texts = ["Нормальный текст.", "", "  ", "Ещё текст."]
        result = merge_transcriptions(texts)
        assert "Нормальный текст." in result
        assert "Ещё текст." in result
        # No double spaces from empty chunks
        assert "  " not in result

    def test_all_empty(self):
        texts = ["", "  ", "\t"]
        result = merge_transcriptions(texts)
        assert result == ""

    def test_whitespace_stripped(self):
        texts = ["  Текст с пробелами  ", " Ещё текст "]
        result = merge_transcriptions(texts)
        assert result == "Текст с пробелами Ещё текст"

    def test_empty_list(self):
        result = merge_transcriptions([])
        assert result == ""


class TestNeedsChunking:
    def test_small_file_no_chunk(self, tmp_path):
        f = tmp_path / "small.mp3"
        f.write_bytes(b"x" * (GROQ_MAX_FILE_BYTES - 1))
        assert needs_chunking(f) is False

    def test_exact_limit_no_chunk(self, tmp_path):
        f = tmp_path / "exact.mp3"
        f.write_bytes(b"x" * GROQ_MAX_FILE_BYTES)
        assert needs_chunking(f) is False

    def test_over_limit_needs_chunk(self, tmp_path):
        f = tmp_path / "large.mp3"
        f.write_bytes(b"x" * (GROQ_MAX_FILE_BYTES + 1))
        assert needs_chunking(f) is True
