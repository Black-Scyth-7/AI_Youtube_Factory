"""Background job models: render jobs and the generic queue job record.

These are the durable record of work, distinct from the transport that carries
it (Celery/RabbitMQ). A row here survives a broker restart and is what the UI
and retry logic read.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.domain_enums import JobStatus, RenderJobKind
from app.models.mixins import EntityMixin
from app.models.types import GUID


class QueueJob(EntityMixin, Base):
    """A unit of background work, independent of the broker that carries it."""

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    queue: Mapped[str] = mapped_column(
        String(64), default="default", nullable=False, index=True
    )
    task_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), default=JobStatus.QUEUED.value, nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Set when a job is deferred or scheduled for retry.
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Broker-side identifier, so a row can be correlated with Celery.
    external_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True
    )

    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def can_retry(self) -> bool:
        """True when a failed job still has attempts left."""
        return self.status == JobStatus.FAILED.value and self.attempts < self.max_attempts


class RenderJob(EntityMixin, Base):
    """A media render for one video: audio, video, thumbnail or subtitles."""

    video_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("video.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    queue_job_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("queue_job.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(
        String(16), default=RenderJobKind.VIDEO.value, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default=JobStatus.QUEUED.value, nullable=False, index=True
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Storage key of the produced artefact, resolved through the storage layer
    # rather than stored as a URL, so the backing provider can change.
    output_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    output_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
