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


def _mock_openrouter_response(text: str) -> MagicMock:
    """Build an httpx.Response mock with the OpenAI/OpenRouter chat-completion shape."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value={
        "choices": [{"message": {"content": text}}]
    })
    return response


class TestGenerateSummary:
    @pytest.mark.asyncio
    async def test_calls_openrouter(self):
        mock_response = _mock_openrouter_response("## 📌 Ключевая мысль\nТест.")

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("src.services.summary.httpx.AsyncClient", return_value=mock_client):
            result = await generate_summary("Тестовый текст", api_key="test-key")

        assert "Ключевая мысль" in result
        assert "Тест." in result
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_summary_uses_template_prompt(self):
        mock_response = _mock_openrouter_response("Summary")

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("src.services.summary.httpx.AsyncClient", return_value=mock_client):
            await generate_summary("Текст для теста", api_key="test-key")

            # The POST payload is the second positional or the `json=` kwarg.
            call = mock_client.post.call_args
            payload = call.kwargs.get("json")
            assert payload is not None
            messages = payload["messages"]
            assert "Текст для теста" in messages[0]["content"]
            # Default model comes from settings.
            assert payload["model"]
