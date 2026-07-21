"""Health/diagnostic worker tasks.

A trivial task used to verify the worker, broker, and result backend are wired
correctly. Real AI pipeline tasks are added in later phases.
"""

from __future__ import annotations

from worker.celery_app import celery_app


@celery_app.task(name="worker.health.ping")
def ping() -> str:
    """Return ``pong`` — a liveness check for the worker."""
    return "pong"
