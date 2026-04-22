"""Prometheus metrics — exposed via /metrics on the FastAPI app.

Only metric *definitions* live here so any process (api/bot/worker) can
import and update them without pulling in FastAPI.
"""
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# We don't fork workers inside the API process (uvicorn is single-process by
# default in our compose), so a shared registry is fine.
REGISTRY = CollectorRegistry()


def _counter(name: str, doc: str, labels: list[str] | None = None) -> Counter:
    return Counter(name, doc, labels or [], registry=REGISTRY)


def _gauge(name: str, doc: str, labels: list[str] | None = None) -> Gauge:
    return Gauge(name, doc, labels or [], registry=REGISTRY)


def _hist(name: str, doc: str, labels: list[str] | None = None, buckets=None) -> Histogram:
    return Histogram(
        name,
        doc,
        labels or [],
        buckets=buckets or (0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600, 1800, 3600),
        registry=REGISTRY,
    )


# Transcriptions
transcriptions_total = _counter(
    "bukvatrans_transcriptions_total",
    "Transcription job completions",
    ["status", "source_type"],
)
transcription_duration_seconds = _hist(
    "bukvatrans_transcription_duration_seconds",
    "Wall-clock duration of a transcription job",
    ["source_type"],
)

# Payments
payments_total = _counter(
    "bukvatrans_payments_total",
    "Payment webhook outcomes",
    ["event", "type"],
)
payment_amount_rub = _counter(
    "bukvatrans_payment_amount_rub_total",
    "Total revenue in rubles by type",
    ["type"],
)

# Queues / infrastructure
dlq_size = _gauge("bukvatrans_dlq_size", "Current Celery DLQ length")
active_transcriptions = _gauge(
    "bukvatrans_active_transcriptions",
    "Jobs currently in pending/processing state",
)

# HTTP (webhooks)
http_requests_total = _counter(
    "bukvatrans_http_requests_total",
    "HTTP requests handled",
    ["path", "status"],
)
http_request_duration_seconds = _hist(
    "bukvatrans_http_request_duration_seconds",
    "HTTP request latency",
    ["path"],
    buckets=(0.01, 0.05, 0.1, 0.3, 1, 3, 10),
)


def render_latest() -> tuple[bytes, str]:
    """Render current metrics. Returns (body, content_type)."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
