"""Tests for the Celery worker configuration."""

from __future__ import annotations

from worker.celery_app import celery_app
from worker.tasks.health import ping


def test_celery_app_is_configured() -> None:
    assert celery_app.main == "ai_youtube_factory"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.task_max_retries == 3


def test_dead_letter_queue_declared() -> None:
    queue_names = {q.name for q in celery_app.conf.task_queues}
    assert "dead_letter" in queue_names
    assert "default" in queue_names


def test_ping_task_runs_eagerly() -> None:
    celery_app.conf.task_always_eager = True
    result = ping.apply()
    assert result.get() == "pong"
