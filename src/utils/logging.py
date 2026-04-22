import logging
import re
from typing import Any, Optional

import sentry_sdk
import structlog
from sentry_sdk.integrations.logging import LoggingIntegration

_BOT_TOKEN_RE = re.compile(r"bot\d{6,}:[A-Za-z0-9_-]{20,}")
_BEARER_RE = re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE)
_SECRET_KEYS = {
    "bot_token",
    "token",
    "authorization",
    "secret",
    "api_key",
    "password",
    "x-telegram-bot-api-secret-token",
    "x-yookassa-signature",
    "yukassa_secret_key",
    "groq_api_key",
    "claude_api_key",
}


def mask_token(value: str) -> str:
    """Mask secret-like strings inside a string value."""
    if not value:
        return value
    masked = _BOT_TOKEN_RE.sub("bot***:***", value)
    masked = _BEARER_RE.sub("Bearer ***", masked)
    return masked


def _redact(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("***REDACTED***" if k.lower() in _SECRET_KEYS else _redact(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    if isinstance(obj, str):
        return mask_token(obj)
    return obj


def _sentry_before_send(event: dict, hint: dict) -> Optional[dict]:
    """Strip potential secrets from Sentry events."""
    try:
        if "request" in event:
            req = event["request"]
            for key in ("data", "query_string", "cookies"):
                if key in req:
                    req[key] = "***REDACTED***"
            if "headers" in req and isinstance(req["headers"], dict):
                req["headers"] = _redact(req["headers"])
        if "extra" in event:
            event["extra"] = _redact(event["extra"])
        if "logentry" in event and "message" in event["logentry"]:
            event["logentry"]["message"] = mask_token(str(event["logentry"]["message"]))
    except Exception:
        return event
    return event


class _RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_token(record.msg)
        return True


def setup_logging() -> None:
    """Configure structlog + Sentry + secret redaction."""
    if not _is_sentry_configured():
        from src.config import settings
        if settings.SENTRY_DSN:
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.ENV,
                traces_sample_rate=0.1,
                profiles_sample_rate=0.1,
                send_default_pii=False,
                before_send=_sentry_before_send,
                integrations=[
                    LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR)
                ],
            )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logging.getLogger().addFilter(_RedactingFilter())

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_job_context(**kwargs: Any) -> None:
    """Bind correlation IDs into the ambient logging context."""
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_job_context() -> None:
    structlog.contextvars.clear_contextvars()


def _is_sentry_configured() -> bool:
    try:
        return bool(sentry_sdk.get_client().dsn)
    except Exception:
        return False
