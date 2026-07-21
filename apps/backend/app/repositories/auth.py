"""Repositories for authentication artifacts."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update

from app.models.auth import (
    EmailVerificationToken,
    OAuthAccount,
    PasswordResetToken,
    RefreshToken,
    Session,
)
from app.repositories.base import BaseRepository


class SessionRepository(BaseRepository[Session]):
    """Data access for login :class:`Session` records."""

    model = Session

    async def list_active_for_user(self, user_id: uuid.UUID) -> list[Session]:
        result = await self.session.execute(
            select(Session).where(
                Session.user_id == user_id, Session.revoked_at.is_(None)
            )
        )
        return list(result.scalars().all())


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Data access for rotating :class:`RefreshToken` records."""

    model = RefreshToken

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke_for_session(self, session_id: uuid.UUID) -> None:
        from datetime import UTC, datetime

        await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.session_id == session_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )


class EmailVerificationTokenRepository(BaseRepository[EmailVerificationToken]):
    """Data access for :class:`EmailVerificationToken`."""

    model = EmailVerificationToken

    async def get_by_hash(self, token_hash: str) -> EmailVerificationToken | None:
        result = await self.session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == token_hash
            )
        )
        return result.scalar_one_or_none()


class PasswordResetTokenRepository(BaseRepository[PasswordResetToken]):
    """Data access for :class:`PasswordResetToken`."""

    model = PasswordResetToken

    async def get_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        result = await self.session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()


class OAuthAccountRepository(BaseRepository[OAuthAccount]):
    """Data access for linked :class:`OAuthAccount` records."""

    model = OAuthAccount

    async def get_by_provider(
        self, provider: str, provider_account_id: str
    ) -> OAuthAccount | None:
        result = await self.session.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_account_id == provider_account_id,
            )
        )
        return result.scalar_one_or_none()
