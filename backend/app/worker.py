"""Celery worker for background tasks.

This handles long-running operations like:
- Syncing cards to Meilisearch
- Price synchronization
- Bulk imports

Usage:
    celery -A app.worker worker --loglevel=info
"""

from celery import Celery

from .config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "tcg_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution settings
    task_acks_late=True,  # Acknowledge after completion (for reliability)
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # One task at a time per worker
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    # Beat schedule (for periodic tasks)
    beat_schedule={
        "sync-cards-to-search": {
            "task": "app.tasks.sync_all_cards_to_search",
            "schedule": 300.0,  # Every 5 minutes
        },
    },
)

# For backwards compatibility
app = celery_app
