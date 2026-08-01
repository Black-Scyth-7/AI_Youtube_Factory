"""Video pipeline models: research, publications, and analytics.

The pipeline turns an idea into a published video and then learns from how it
performed. Research notes and analytics snapshots are kept as first-class rows
rather than blobs on the video, so an agent can query across them.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.domain_enums import PipelineStage, PublicationStatus
from app.models.mixins import EntityMixin
from app.models.types import GUID


class ResearchNote(EntityMixin, Base):
    """A finding gathered while researching a video's topic."""

    video_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("video.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # 0..1 confidence from whichever agent or tool produced the note.
    relevance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )


class PipelineRun(EntityMixin, Base):
    """One attempt to take a video through the pipeline."""

    video_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("video.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(
        String(24), default=PipelineStage.RESEARCH.value, nullable=False, index=True
    )
    # Set when a stage fails; cleared when it is retried successfully.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Artefacts produced along the way, keyed by stage.
    artifacts: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class Publication(EntityMixin, Base):
    """A video as it exists on a destination platform."""

    __table_args__ = (
        # One live publication per video per platform; a re-publish updates it.
        UniqueConstraint("video_id", "platform", name="uq_publication_video_id_platform"),
    )

    video_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("video.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(
        String(32), default="youtube", nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default=PublicationStatus.DRAFT.value, nullable=False, index=True
    )
    external_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    snapshots: Mapped[list[AnalyticsRecord]] = relationship(
        back_populates="publication", cascade="all, delete-orphan"
    )


class AnalyticsRecord(EntityMixin, Base):
    """One day's metrics for a publication."""

    __table_args__ = (
        # Re-fetching a day updates the row rather than appending a duplicate.
        UniqueConstraint(
            "publication_id",
            "measured_on",
            name="uq_analytics_publication_id_measured_on",
        ),
    )

    publication_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("publication.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    measured_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    views: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    watch_time_seconds: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    impressions: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    publication: Mapped[Publication] = relationship(back_populates="snapshots")

    @property
    def click_through_rate(self) -> float:
        """Views per impression; zero impressions means no data, not a zero rate."""
        return self.views / self.impressions if self.impressions else 0.0


class PerformanceLesson(EntityMixin, Base):
    """What the system concluded from a video's performance.

    The 'learning' end of the loop: durable, queryable observations an agent can
    consult when planning the next video.
    """

    video_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("video.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )
    dimension: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    observation: Mapped[str] = mapped_column(Text, nullable=False)
    # 0..1 — how strongly the data supports the observation.
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
