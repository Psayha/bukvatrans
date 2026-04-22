import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.summary import generate_summary, _prepare_text, MAX_TEXT_LENGTH


class TestPrepareText:
    def test_short_text_unchanged(self):
        text = "Короткий текст"
        assert _prepare_text(text) == text

    def test_exactly_at_limit_unchanged(self):
        text = "x" * MAX_TEXT_LENGTH
        assert _prepare_text(text) == text

    def test_long_text_truncated(self):
        # Must be significantly over limit so 3×50k chunks + markers < original
        text = "x" * (MAX_TEXT_LENGTH * 2)
        result = _prepare_text(text)
        assert len(result) < len(text)
        assert "пропущена часть текста" in result

    def test_long_text_has_three_parts(self):
        text = "a" * (MAX_TEXT_LENGTH + 10000)
        result = _prepare_text(text)
        # Should contain two skip markers
        assert result.count("пропущена часть текста") == 2

    def test_first_chunk_preserved(self):
        text = "START" + "x" * (MAX_TEXT_LENGTH)
        result = _prepare_text(text)
        assert result.startswith("START")

    def test_last_chunk_preserved(self):
        text = "x" * (MAX_TEXT_LENGTH) + "END"
        result = _prepare_text(text)
        assert "END" in result


class TestGenerateSummary:
    @pytest.mark.asyncio
    async def test_calls_claude_api(self):
        mock_content = MagicMock()
        mock_content.text = "## 📌 Ключевая мысль\nТест."
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        with patch("src.services.summary.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            result = await generate_summary("Тестовый текст", api_key="test-key")

        assert "Ключевая мысль" in result
        assert "Тест." in result

    @pytest.mark.asyncio
    async def test_summary_uses_template_prompt(self):
        mock_content = MagicMock()
        mock_content.text = "Summary"
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        with patch("src.services.summary.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_client

            await generate_summary("Текст для теста", api_key="test-key")

            call_args = mock_client.messages.create.call_args
            messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
            assert "Текст для теста" in messages[0]["content"]
