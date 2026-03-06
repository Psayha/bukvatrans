import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from src.api.main import app
from src.api.webhooks import _is_yukassa_ip


def make_client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

WEBHOOK_PAYLOAD_SUCCESS = {
    "type": "notification",
    "event": "payment.succeeded",
    "object": {
        "id": "test_payment_123",
        "status": "succeeded",
        "amount": {"value": "649.00", "currency": "RUB"},
        "metadata": {
            "user_id": "123456789",
            "plan_key": "basic_monthly",
        },
        "paid": True,
    },
}

WEBHOOK_PAYLOAD_CANCELLED = {
    "type": "notification",
    "event": "payment.canceled",
    "object": {
        "id": "test_payment_456",
        "status": "canceled",
        "amount": {"value": "649.00", "currency": "RUB"},
        "metadata": {"user_id": "123456789"},
    },
}


class TestYukassaIPValidation:
    def test_yukassa_ip_valid_single(self):
        assert _is_yukassa_ip("77.75.156.11") is True

    def test_yukassa_ip_valid_single_2(self):
        assert _is_yukassa_ip("77.75.156.35") is True

    def test_yukassa_ip_valid_subnet_1(self):
        assert _is_yukassa_ip("185.71.76.1") is True

    def test_yukassa_ip_valid_subnet_2(self):
        assert _is_yukassa_ip("185.71.77.1") is True

    def test_non_yukassa_ip_rejected(self):
        assert _is_yukassa_ip("1.2.3.4") is False

    def test_empty_ip_rejected(self):
        assert _is_yukassa_ip("") is False

    def test_invalid_ip_rejected(self):
        assert _is_yukassa_ip("not-an-ip") is False


class TestYukassaWebhook:
    @pytest.mark.asyncio
    async def test_invalid_ip_returns_403(self):
        async with make_client() as client:
            response = await client.post(
                "/webhooks/yukassa",
                json=WEBHOOK_PAYLOAD_SUCCESS,
                headers={"X-Real-IP": "1.2.3.4"},
            )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_valid_ip_processes_payment(self):
        with patch("src.api.webhooks._handle_payment_succeeded", new_callable=AsyncMock) as mock_handle:
            with patch("src.api.webhooks.get_transaction_by_yukassa_id", return_value=None, new_callable=AsyncMock):
                async with make_client() as client:
                    response = await client.post(
                        "/webhooks/yukassa",
                        json=WEBHOOK_PAYLOAD_SUCCESS,
                        headers={"X-Real-IP": "185.71.76.1"},
                    )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_idempotency_no_double_processing(self):
        from src.db.models.transaction import Transaction
        existing = Transaction(
            id="tx-1",
            user_id=123456789,
            type="subscription",
            status="success",
            yukassa_id="test_payment_123",
        )
        with patch(
            "src.api.webhooks.get_transaction_by_yukassa_id",
            return_value=existing,
            new_callable=AsyncMock,
        ):
            with patch("src.api.webhooks._handle_payment_succeeded", new_callable=AsyncMock) as mock_handle:
                async with make_client() as client:
                    response = await client.post(
                        "/webhooks/yukassa",
                        json=WEBHOOK_PAYLOAD_SUCCESS,
                        headers={"X-Real-IP": "185.71.76.1"},
                    )
                # Should not process again
                mock_handle.assert_not_called()
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cancelled_event_handled(self):
        with patch("src.api.webhooks._handle_payment_cancelled", new_callable=AsyncMock):
            with patch("src.api.webhooks.get_transaction_by_yukassa_id", return_value=None, new_callable=AsyncMock):
                async with make_client() as client:
                    response = await client.post(
                        "/webhooks/yukassa",
                        json=WEBHOOK_PAYLOAD_CANCELLED,
                        headers={"X-Real-IP": "185.71.76.1"},
                    )
        assert response.status_code == 200
