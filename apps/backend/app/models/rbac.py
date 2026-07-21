"""Role-based access control models: permissions and roles."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import AuditMixin
from app.models.types import GUID

# Association table linking roles to permissions (many-to-many).
role_permissions = Table(
    "role_permission",
    Base.metadata,
    Column(
        "role_id",
        GUID(),
        ForeignKey("role.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        GUID(),
        ForeignKey("permission.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Permission(AuditMixin, Base):
    """A granular capability, e.g. ``video.create``."""

    slug: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)

    roles: Mapped[list[Role]] = relationship(
        secondary=role_permissions, back_populates="permissions"
    )


class Role(AuditMixin, Base):
    """A named set of permissions, scoped globally or to an organization.

    ``organization_id`` is null for the built-in system role templates and set
    for organization-specific custom roles.
    """

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_role_org_slug"),
    )

    slug: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions, back_populates="roles", lazy="selectin"
    )
