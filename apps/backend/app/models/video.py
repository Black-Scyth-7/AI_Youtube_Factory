"""Video and video-version models."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.domain_enums import VideoStatus
from app.models.mixins import EntityMixin
from app.models.types import GUID


class Video(EntityMixin, Base):
    """A video belonging to a project, optionally targeting a channel."""

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("channel.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=VideoStatus.DRAFT.value, nullable=False, index=True
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    versions: Mapped[list[VideoVersion]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        foreign_keys="VideoVersion.video_id",
    )


class VideoVersion(EntityMixin, Base):
    """An immutable-ish snapshot of a video's script/content at a version."""

    __table_args__ = (
        UniqueConstraint("video_id", "version_number", name="uq_video_version_num"),
    )

    video_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("video.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    script: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=VideoStatus.DRAFT.value, nullable=False
    )

    video: Mapped[Video] = relationship(
        back_populates="versions", foreign_keys=[video_id]
    )
