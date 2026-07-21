"""Session and token lifecycle service.

Creates login sessions, issues JWT access tokens + opaque refresh tokens, rotates
refresh tokens on use (with replay detection), and revokes sessions/tokens.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions.base import UnauthorizedError
from app.models.auth import RefreshToken, Session
from app.models.user import User
from app.repositories.auth import RefreshTokenRepository, SessionRepository
from app.security.jwt import create_access_token
from app.security.tokens import generate_token, hash_token


@dataclass(slots=True, frozen=True)
class RequestContext:
    """Client metadata captured for a session."""

    ip_address: str | None = None
    user_agent: str | None = None
    browser: str | None = None
    os: str | None = None
    device: str | None = None


@dataclass(slots=True, frozen=True)
class IssuedTokens:
    """A freshly issued access/refresh token pair."""

    access_token: str
    refresh_token: str
    expires_in: int


class TokenService:
    """Manages sessions and access/refresh tokens."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sessions = SessionRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    async def create_session(self, user: User, ctx: RequestContext) -> Session:
        """Create and persist a new login session for ``user``."""
        now = datetime.now(UTC)
        session = Session(
            user_id=user.id,
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
            browser=ctx.browser,
            os=ctx.os,
            device=ctx.device,
            last_activity=now,
        )
        return await self.sessions.add(session)

    async def issue_tokens(self, user: User, session: Session) -> IssuedTokens:
        """Issue an access token and a new refresh token for ``session``."""
        access = create_access_token(user_id=user.id, session_id=session.id)
        raw_refresh = generate_token()
        refresh = RefreshToken(
            user_id=user.id,
            session_id=session.id,
            token_hash=hash_token(raw_refresh),
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.refresh_token_expire_days),
        )
        await self.refresh_tokens.add(refresh)
        return IssuedTokens(
            access_token=access,
            refresh_token=raw_refresh,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def rotate(self, raw_refresh: str) -> IssuedTokens:
        """Validate and rotate a refresh token, returning a new pair.

        Detects reuse of an already-rotated token and, on detection, revokes the
        whole session (defense against token theft/replay).
        """
        token = await self.refresh_tokens.get_by_hash(hash_token(raw_refresh))
        if token is None:
            raise UnauthorizedError("Invalid refresh token.")

        now = datetime.now(UTC)
        if token.revoked_at is not None or token.rotated_to is not None:
            # Reuse of a consumed token → possible theft. Revoke the session.
            await self.refresh_tokens.revoke_for_session(token.session_id)
            session = await self.sessions.get(token.session_id)
            if session is not None:
                session.revoked_at = now
            await self.session.flush()
            raise UnauthorizedError("Refresh token has already been used.")

        if _as_utc(token.expires_at) < now:
            raise UnauthorizedError("Refresh token has expired.")

        session = await self.sessions.get(token.session_id)
        if session is None or session.revoked_at is not None:
            raise UnauthorizedError("Session is no longer active.")

        user = await self.session.get(User, token.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("User is no longer active.")

        # Issue the successor, then link + revoke the old token.
        issued = await self.issue_tokens(user, session)
        new_hash = hash_token(issued.refresh_token)
        successor = await self.refresh_tokens.get_by_hash(new_hash)
        token.revoked_at = now
        token.rotated_to = successor.id if successor else None
        session.last_activity = now
        await self.session.flush()
        return issued

    async def revoke_session(self, session_id: uuid.UUID) -> None:
        """Revoke a session and all its refresh tokens."""
        session = await self.sessions.get(session_id)
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(UTC)
        await self.refresh_tokens.revoke_for_session(session_id)
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """Revoke every active session for a user."""
        for session in await self.sessions.list_active_for_user(user_id):
            await self.revoke_session(session.id)


def _as_utc(value: datetime) -> datetime:
    """Treat naive datetimes (SQLite) as UTC for comparison."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)
