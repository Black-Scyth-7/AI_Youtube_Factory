"""Organization and membership models."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import MemberStatus
from app.models.mixins import AuditMixin
from app.models.types import GUID


class Organization(AuditMixin, Base):
    """A tenant that owns channels, projects, teams, and members."""

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    members: Mapped[list[OrganizationMember]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class OrganizationMember(AuditMixin, Base):
    """A user's membership in an organization, with an assigned role."""

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member_org_user"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("role.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default=MemberStatus.ACTIVE.value, nullable=False
    )

    organization: Mapped[Organization] = relationship(back_populates="members")
