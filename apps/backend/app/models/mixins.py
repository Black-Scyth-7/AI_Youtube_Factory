"""Reusable ORM mixins.

Provides the columns every persistent entity should carry:

* :class:`UUIDPrimaryKeyMixin` — UUID primary keys (never integer ids).
* :class:`TimestampMixin` — ``created_at`` / ``updated_at`` audit columns.
* :class:`SoftDeleteMixin` — ``deleted_at`` for soft deletes.
* :class:`AuditMixin` — combines all three, the default base for entities.

Uses the portable :class:`GUID` type so models run natively on PostgreSQL and
on other backends (SQLite) for tests.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.types import GUID


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key generated on the application side."""

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """Adds server-managed created/updated audit timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Adds a nullable ``deleted_at`` for soft deletes."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    @property
    def is_deleted(self) -> bool:
        """Return ``True`` if the row has been soft-deleted."""
        return self.deleted_at is not None


class AuditMixin(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Convenience mixin combining UUID PK, timestamps, and soft delete."""
