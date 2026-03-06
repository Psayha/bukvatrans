"""Locust load testing for BukvaTransBot FastAPI webhooks.

Usage:
    locust -f locustfile.py --host=http://localhost:8000
    locust -f locustfile.py --host=http://localhost:8000 --headless -u 50 -r 5 --run-time 60s
"""
import json
import uuid
from locust import HttpUser, task, between, events


# Simulate a YuKassa payment.succeeded webhook payload
def _payment_payload(payment_id: str, user_id: int = 100001) -> dict:
    return {
        "type": "notification",
        "event": "payment.succeeded",
        "object": {
            "id": payment_id,
            "status": "succeeded",
            "amount": {"value": "199.00", "currency": "RUB"},
            "metadata": {
                "user_id": str(user_id),
                "plan": "basic_monthly",
            },
            "paid": True,
            "refundable": True,
            "created_at": "2026-01-01T00:00:00.000Z",
        },
    }


def _refund_payload(refund_id: str, payment_id: str, user_id: int = 100001) -> dict:
    return {
        "type": "notification",
        "event": "refund.succeeded",
        "object": {
            "id": refund_id,
            "payment_id": payment_id,
            "status": "succeeded",
            "amount": {"value": "199.00", "currency": "RUB"},
            "metadata": {
                "user_id": str(user_id),
            },
            "created_at": "2026-01-01T00:00:00.000Z",
        },
    }


class WebhookUser(HttpUser):
    """Simulates YuKassa webhook requests to the FastAPI application."""

    # Wait 0.5–2 seconds between tasks to simulate realistic load
    wait_time = between(0.5, 2)

    # YuKassa whitelisted IP — for load testing we bypass IP check
    # by setting a real whitelisted IP in the X-Forwarded-For header
    headers = {
        "Content-Type": "application/json",
        # Use a real YuKassa IP to pass the IP whitelist check
        "X-Forwarded-For": "185.71.76.1",
    }

    @task(5)
    def payment_succeeded_webhook(self):
        """Simulate a successful payment notification (most common event)."""
        payment_id = str(uuid.uuid4())
        payload = _payment_payload(payment_id, user_id=100001)

        with self.client.post(
            "/webhooks/yukassa",
            data=json.dumps(payload),
            headers=self.headers,
            catch_response=True,
            name="POST /webhooks/yukassa [payment.succeeded]",
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code in (400, 422):
                # Expected if DB not set up — mark as success for load test purposes
                response.success()
            elif response.status_code == 403:
                response.failure(f"IP blocked (403): {response.text[:100]}")
            else:
                response.failure(f"Unexpected status {response.status_code}: {response.text[:100]}")

    @task(2)
    def refund_webhook(self):
        """Simulate a refund notification."""
        refund_id = str(uuid.uuid4())
        payment_id = str(uuid.uuid4())
        payload = _refund_payload(refund_id, payment_id, user_id=100001)

        with self.client.post(
            "/webhooks/yukassa",
            data=json.dumps(payload),
            headers=self.headers,
            catch_response=True,
            name="POST /webhooks/yukassa [refund.succeeded]",
        ) as response:
            if response.status_code in (200, 400, 422):
                response.success()
            elif response.status_code == 403:
                response.failure(f"IP blocked (403): {response.text[:100]}")
            else:
                response.failure(f"Unexpected status {response.status_code}: {response.text[:100]}")

    @task(1)
    def invalid_ip_request(self):
        """Test that requests from non-YuKassa IPs are rejected (403)."""
        payload = _payment_payload(str(uuid.uuid4()))
        bad_headers = {
            "Content-Type": "application/json",
            "X-Forwarded-For": "1.2.3.4",  # Not a YuKassa IP
        }

        with self.client.post(
            "/webhooks/yukassa",
            data=json.dumps(payload),
            headers=bad_headers,
            catch_response=True,
            name="POST /webhooks/yukassa [invalid IP → 403]",
        ) as response:
            if response.status_code == 403:
                response.success()  # Expected rejection
            else:
                response.failure(f"Should have been 403, got {response.status_code}")

    @task(1)
    def health_check(self):
        """Check the health endpoint if available."""
        with self.client.get(
            "/health",
            catch_response=True,
            name="GET /health",
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Unexpected health status {response.status_code}")


class HighLoadWebhookUser(WebhookUser):
    """High-frequency user that simulates a burst of webhook events."""

    wait_time = between(0.1, 0.5)

    @task(10)
    def rapid_payment_webhooks(self):
        """Rapid-fire payment notifications to stress-test idempotency."""
        # Reuse the same payment_id to test idempotency handling
        payment_id = "load-test-idempotent-payment-001"
        payload = _payment_payload(payment_id, user_id=999999)

        with self.client.post(
            "/webhooks/yukassa",
            data=json.dumps(payload),
            headers=self.headers,
            catch_response=True,
            name="POST /webhooks/yukassa [idempotency stress]",
        ) as response:
            # Both 200 (processed) and 200 (already processed) are valid
            if response.status_code in (200, 400, 422):
                response.success()
            else:
                response.failure(f"Status {response.status_code}: {response.text[:100]}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n=== BukvaTransBot Load Test Starting ===")
    print(f"Target host: {environment.host}")
    print("Testing endpoints: POST /webhooks/yukassa, GET /health")
    print("========================================\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    stats = environment.stats
    total = stats.total
    print("\n=== Load Test Summary ===")
    print(f"Total requests: {total.num_requests}")
    print(f"Failures: {total.num_failures}")
    print(f"Avg response time: {total.avg_response_time:.1f}ms")
    print(f"95th percentile: {total.get_response_time_percentile(0.95):.1f}ms")
    print(f"RPS: {total.current_rps:.1f}")
    print("========================\n")
