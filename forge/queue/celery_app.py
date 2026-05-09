"""Celery configuration for the Forge build worker."""

from celery import Celery

from forge.config import settings

celery_app = Celery(
    "forge",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    # Force single-task processing to respect Gemini RPM (15 RPM on free tier)
    worker_concurrency=1,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    # 5 minute timeout per build pipeline
    task_time_limit=360,
    task_soft_time_limit=300,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
)
