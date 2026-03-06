from celery import Celery
from celery.schedules import crontab

from src.config import settings

app = Celery("transcribe_bot", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "src.worker.tasks.transcription.*": {"queue": "transcription"},
        "src.worker.tasks.summary.*": {"queue": "summary"},
        "src.worker.tasks.maintenance.*": {"queue": "maintenance"},
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
