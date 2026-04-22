from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_ready, worker_shutting_down, task_prerun, task_postrun
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

from src.config import settings
from src.utils.logging import (
    _sentry_before_send,
    bind_job_context,
    clear_job_context,
    setup_logging,
)

setup_logging()

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENV,
        traces_sample_rate=0.1,
        send_default_pii=False,
        before_send=_sentry_before_send,
        integrations=[CeleryIntegration()],
    )

app = Celery("transcribe_bot", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    # At-least-once delivery: re-queue on worker loss, ack only after success.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Hard and soft timeouts protect against stuck Groq/yt-dlp calls.
    task_soft_time_limit=settings.CELERY_SOFT_TIME_LIMIT,
    task_time_limit=settings.CELERY_TIME_LIMIT,
    # Graceful shutdown: wait long enough for in-flight transcription tasks
    # to finish (CELERY_TIME_LIMIT + small buffer). Matches docker-compose
    # stop_grace_period so SIGKILL doesn't chop long jobs in half.
    worker_shutdown_timeout=settings.CELERY_TIME_LIMIT + 60,
    broker_connection_retry_on_startup=True,
    task_routes={
        "src.worker.tasks.transcription.*": {"queue": "transcription"},
        "src.worker.tasks.summary.*": {"queue": "summary"},
        "src.worker.tasks.maintenance.*": {"queue": "maintenance"},
        "src.worker.tasks.stats.*": {"queue": "maintenance"},
    },
)

app.conf.beat_schedule = {
    "expire_subscriptions": {
        "task": "src.worker.tasks.maintenance.expire_subscriptions",
        "schedule": 3600,
    },
    "cleanup_tmp_files": {
        "task": "src.worker.tasks.maintenance.cleanup_tmp_files",
        "schedule": 1800,
    },
    "purge_old_transcription_text": {
        "task": "src.worker.tasks.maintenance.purge_old_transcription_text",
        "schedule": crontab(hour=3, minute=30),
    },
    "check_dlq": {
        "task": "src.worker.tasks.maintenance.check_dead_letter_queue",
        "schedule": 300,
    },
    "daily_stats": {
        "task": "src.worker.tasks.stats.send_daily_report",
        "schedule": crontab(hour=9, minute=0),
    },
}

app.autodiscover_tasks(["src.worker.tasks"])


@task_prerun.connect
def _bind_task_context(task_id=None, task=None, args=None, kwargs=None, **_):
    bind_job_context(
        task_id=task_id,
        task_name=getattr(task, "name", ""),
    )


@task_postrun.connect
def _unbind_task_context(**_):
    clear_job_context()


@worker_ready.connect
def _on_worker_ready(**_):
    import logging
    logging.getLogger(__name__).info("worker_ready")


@worker_shutting_down.connect
def _on_shutdown(sig=None, how=None, **_):
    import logging
    logging.getLogger(__name__).info("worker_shutting_down sig=%s how=%s", sig, how)
