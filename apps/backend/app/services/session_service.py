"""Session management service (list/terminate active sessions)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import NotFoundError
from app.models.auth import Session
from app.models.enums import AuditAction
from app.repositories.auth import SessionRepository
from app.services.audit import AuditService
from app.services.token_service import RequestContext, TokenService


def parse_user_agent(user_agent: str | None) -> RequestContext:
    """Derive browser/OS/device from a User-Agent header (best-effort)."""
    if not user_agent:
        return RequestContext()
    try:
        from user_agents import parse

        ua = parse(user_agent)
        device = "mobile" if ua.is_mobile else "tablet" if ua.is_tablet else "desktop"
        return RequestContext(
            user_agent=user_agent,
            browser=ua.browser.family,
            os=ua.os.family,
            device=device,
        )
    except Exception:
        return RequestContext(user_agent=user_agent)


class SessionService:
    """Lists and terminates a user's login sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sessions = SessionRepository(session)
        self.tokens = TokenService(session)
        self.audit = AuditService(session)

    async def list_active(self, user_id: uuid.UUID) -> list[Session]:
        return await self.sessions.list_active_for_user(user_id)

    async def terminate(self, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        session = await self.sessions.get(session_id)
        if session is None or session.user_id != user_id:
            raise NotFoundError("Session not found.")
        await self.tokens.revoke_session(session_id)
        await self.audit.record(
            AuditAction.SESSION_REVOKED, actor_id=user_id, target_id=str(session_id)
        )

    async def terminate_all(self, user_id: uuid.UUID) -> None:
        await self.tokens.revoke_all_for_user(user_id)
        await self.audit.record(AuditAction.SESSIONS_REVOKED_ALL, actor_id=user_id)
