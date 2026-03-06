import logging
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration


def setup_logging() -> None:
    """Configure structlog + Sentry."""
    if not _is_sentry_configured():
        from src.config import settings
        if settings.SENTRY_DSN:
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.ENV,
                traces_sample_rate=0.1,
                profiles_sample_rate=0.1,
                integrations=[
                    LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR)
                ],
            )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _is_sentry_configured() -> bool:
    try:
        return bool(sentry_sdk.get_client().dsn)
    except Exception:
        return False
