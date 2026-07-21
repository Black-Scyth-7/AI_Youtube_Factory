"""Celery application factory.

Configures the Celery app with RabbitMQ as the broker and Redis as the result
backend. Establishes the retry policy, a dead-letter queue for exhausted tasks,
and a Beat schedule placeholder for future scheduled AI jobs. No business jobs
are implemented in Phase 01.
"""

from __future__ import annotations

from celery import Celery
from kombu import Exchange, Queue

from worker.config import get_worker_settings

settings = get_worker_settings()


def create_celery_app() -> Celery:
    """Build and configure the Celery application."""
    app = Celery("ai_youtube_factory")

    app.conf.update(
        broker_url=settings.rabbitmq_url,
        result_backend=settings.redis_url,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        # Sensible default retry policy for transient failures.
        task_default_retry_delay=10,
        task_max_retries=3,
        # Declare the default and dead-letter queues. Failed tasks that exhaust
        # retries can be routed to the DLQ by later phases.
        task_queues=(
            Queue(
                settings.task_default_queue,
                Exchange(settings.task_default_queue),
                routing_key=settings.task_default_queue,
                queue_arguments={
                    "x-dead-letter-exchange": settings.task_dead_letter_queue,
                },
            ),
            Queue(
                settings.task_dead_letter_queue,
                Exchange(settings.task_dead_letter_queue),
                routing_key=settings.task_dead_letter_queue,
            ),
        ),
        task_default_queue=settings.task_default_queue,
        # Beat schedule placeholder — scheduled AI jobs are added in later phases.
        beat_schedule={},
    )

    app.autodiscover_tasks(["worker.tasks"])
    return app


celery_app = create_celery_app()
