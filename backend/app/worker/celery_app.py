"""Celery application.

Broker/result backend and eager mode come from config. Beat is configured with a
single periodic dispatcher that fires due scheduled workflows every
``beat_dispatch_interval_seconds``.
"""

from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "copilot",
    # "memory://" keeps import/eager mode working when no broker is configured.
    broker=settings.broker_url or "memory://",
    backend=settings.result_backend or "cache+memory://",
)

celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_store_eager_result=True,
    timezone="UTC",
    task_default_queue="copilot",
    beat_schedule={
        "dispatch-due-workflows": {
            "task": "app.worker.tasks.dispatch_due_workflows",
            "schedule": settings.beat_dispatch_interval_seconds,
        }
    },
)

# Ensure task definitions are registered when the app is imported.
celery_app.autodiscover_tasks(["app.worker"])
