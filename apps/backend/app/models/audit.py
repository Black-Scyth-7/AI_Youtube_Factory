"""Audit log model."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import GUID


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An immutable record of a security-relevant action.

    Audit records are append-only, so they use timestamps + UUID PK but not the
    soft-delete mixin.
    """

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
