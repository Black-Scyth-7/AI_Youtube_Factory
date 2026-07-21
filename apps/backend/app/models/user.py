"""User and profile models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import AuditMixin
from app.models.types import GUID


class User(AuditMixin, Base):
    """A platform user (identity + authentication state)."""

    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Nullable: OAuth-only accounts have no local password.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    locale: Mapped[str] = mapped_column(String(16), default="en", nullable=False)

    profile: Mapped[Profile | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Profile(AuditMixin, Base):
    """Extended, optional profile information for a user."""

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    bio: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship(back_populates="profile")
