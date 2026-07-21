"""Workspace, project, and channel models."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.domain_enums import ProjectStatus
from app.models.mixins import EntityMixin
from app.models.types import GUID


class Workspace(EntityMixin, Base):
    """A workspace groups projects and media within an organization."""

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_workspace_org_slug"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    projects: Mapped[list[Project]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class Project(EntityMixin, Base):
    """A project is a unit of content work within a workspace."""

    __table_args__ = (
        UniqueConstraint("workspace_id", "slug", name="uq_project_ws_slug"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default=ProjectStatus.ACTIVE.value, nullable=False, index=True
    )

    workspace: Mapped[Workspace] = relationship(back_populates="projects")
    channels: Mapped[list[Channel]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Channel(EntityMixin, Base):
    """A connected YouTube channel scoped to a project."""

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    youtube_channel_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    handle: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped[Project] = relationship(back_populates="channels")
