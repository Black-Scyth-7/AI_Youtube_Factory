"""Infrastructure models: feature flags and activity log."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.domain_enums import FeatureFlagScope
from app.models.mixins import EntityMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import GUID


class FeatureFlag(EntityMixin, Base):
    """A feature flag with global/org/user scope and percentage rollout."""

    key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scope: Mapped[str] = mapped_column(
        String(32), default=FeatureFlagScope.GLOBAL.value, nullable=False
    )
    rollout_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Explicit allow-list of organization/user ids the flag applies to.
    targets: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class ActivityLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only record of user/system activity (distinct from the security
    audit log): coarser-grained product activity for timelines and analytics."""

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
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
