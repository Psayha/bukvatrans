"""Celery task package.

Importing each task module here is what actually registers the `@app.task`
decorators with the Celery app. `autodiscover_tasks(['src.worker.tasks'])`
would need a file literally named `tasks.py` under this package; we use
one file per queue instead (transcription/summary/maintenance/stats), so
we import them explicitly.
"""
from src.worker.tasks import (  # noqa: F401 — imported for side effects
    maintenance,
    stats,
    summary,
    transcription,
)
