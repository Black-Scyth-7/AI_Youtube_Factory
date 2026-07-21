"""Worker configuration.

Reads broker/result-backend settings from the environment so the worker shares
the same infrastructure as the API without importing the backend package. Values
are validated on load via ``pydantic-settings``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """Validated Celery worker settings."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")

    # Celery uses RabbitMQ as the broker and Redis as the result backend.
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672//")
    redis_url: str = Field(default="redis://localhost:6379/1")

    task_default_queue: str = Field(default="default")
    task_dead_letter_queue: str = Field(default="dead_letter")


@lru_cache
def get_worker_settings() -> WorkerSettings:
    """Return the cached worker settings singleton."""
    return WorkerSettings()
