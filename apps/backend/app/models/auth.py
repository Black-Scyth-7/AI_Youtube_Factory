"""Authentication artifacts: sessions, refresh tokens, verification/reset tokens,
and linked OAuth accounts.

Secret token values are never stored in plaintext — only their SHA-256 hashes
are persisted, so a database compromise does not leak usable tokens.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import AuditMixin
from app.models.types import GUID


class Session(AuditMixin, Base):
    """A logical login session bound to a device/browser."""

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    browser: Mapped[str | None] = mapped_column(String(128), nullable=True)
    os: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_activity: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )


class RefreshToken(AuditMixin, Base):
    """A rotating refresh token bound to a session.

    ``token_hash`` stores the SHA-256 of the opaque token. ``rotated_to`` links a
    consumed token to its successor for replay detection.
    """

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("session.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rotated_to: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class EmailVerificationToken(AuditMixin, Base):
    """A single-use email verification token (stored hashed)."""

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PasswordResetToken(AuditMixin, Base):
    """A single-use password reset token (stored hashed)."""

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OAuthAccount(AuditMixin, Base):
    """A link between a local user and an external OAuth identity."""

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_account_id", name="uq_oauth_provider_account"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    access_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(String(2048), nullable=True)
