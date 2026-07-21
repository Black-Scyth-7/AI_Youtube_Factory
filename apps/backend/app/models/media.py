"""Folder, media file, and tag models."""

from __future__ import annotations

import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.domain_enums import MediaStatus
from app.models.mixins import EntityMixin
from app.models.types import GUID

# Many-to-many between videos and tags.
video_tags = Table(
    "video_tag",
    Base.metadata,
    Column(
        "video_id", GUID(), ForeignKey("video.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("tag_id", GUID(), ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
)


class Folder(EntityMixin, Base):
    """A hierarchical folder for organizing media within a workspace."""

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("folder.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False, default="/")


class MediaFile(EntityMixin, Base):
    """A stored media asset with dedup hash and storage pointer."""

    __table_args__ = (UniqueConstraint("workspace_id", "sha256", name="uq_media_ws_sha"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("folder.id", ondelete="SET NULL"), nullable=True, index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), default=MediaStatus.READY.value, nullable=False
    )


class Tag(EntityMixin, Base):
    """A reusable label scoped to an organization."""

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_tag_org_slug"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)

    videos: Mapped[list[object]] = relationship(
        "Video", secondary=video_tags, lazy="selectin"
    )
