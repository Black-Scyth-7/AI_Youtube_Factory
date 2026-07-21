"""Organization invitation model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import InvitationStatus
from app.models.mixins import AuditMixin
from app.models.types import GUID


class Invitation(AuditMixin, Base):
    """An invitation for a user (by email) to join an organization with a role."""

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("role.id", ondelete="RESTRICT"), nullable=False
    )
    invited_by_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default=InvitationStatus.PENDING.value, nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
