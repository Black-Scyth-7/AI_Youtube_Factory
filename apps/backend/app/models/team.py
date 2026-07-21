"""Team and team-membership models."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import AuditMixin
from app.models.types import GUID


class Team(AuditMixin, Base):
    """A group within an organization."""

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_team_org_slug"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)

    members: Mapped[list[TeamMember]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class TeamMember(AuditMixin, Base):
    """A user's membership in a team, with a role."""

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_member_team_user"),
    )

    team_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("team.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("role.id", ondelete="RESTRICT"), nullable=False
    )

    team: Mapped[Team] = relationship(back_populates="members")
