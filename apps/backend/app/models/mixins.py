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
from typing import Any

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

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
    """Convenience mixin combining UUID PK, timestamps, and soft delete.

    Used by the Phase 02 identity models. New Phase 03 domain entities use
    :class:`EntityMixin`, which additionally carries optimistic-lock versioning
    and ``created_by`` / ``updated_by`` actor columns.
    """


class VersionMixin:
    """Adds an integer ``version`` column for optimistic concurrency control."""

    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )


class ActorMixin:
    """Adds ``created_by`` / ``updated_by`` user-reference columns."""

    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class EntityMixin(
    UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, VersionMixin, ActorMixin
):
    """Full audit surface for domain entities.

    Combines UUID PK, timestamps, soft delete, optimistic-lock ``version``, and
    actor columns. The mapper is configured to use ``version`` for optimistic
    locking so concurrent ORM updates raise ``StaleDataError``.
    """

    @declared_attr.directive
    def __mapper_args__(cls) -> dict[str, Any]:  # noqa: N805
        return {"version_id_col": cls.version}
