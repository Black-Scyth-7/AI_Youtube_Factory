"""Authentication and authorization dependencies.

Resolves the current user from a Bearer access token (validating the underlying
session is still active), exposes request metadata, and provides a reusable RBAC
dependency that enforces a required permission against a path organization id.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.db import get_db_session
from app.exceptions.base import ForbiddenError, UnauthorizedError
from app.models.user import User
from app.security.jwt import decode_access_token
from app.services.rbac import RBACService
from app.services.session_service import parse_user_agent
from app.services.token_service import RequestContext

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_request_context(request: Request) -> RequestContext:
    """Build a :class:`RequestContext` from the incoming request headers."""
    ctx = parse_user_agent(request.headers.get("user-agent"))
    client_ip = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else client_ip
    return RequestContext(
        ip_address=ip,
        user_agent=ctx.user_agent,
        browser=ctx.browser,
        os=ctx.os,
        device=ctx.device,
    )


RequestCtx = Annotated[RequestContext, Depends(get_request_context)]


async def get_current_user(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    """Resolve and return the authenticated user, or raise 401."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Authentication credentials were not provided.")

    claims = decode_access_token(credentials.credentials)

    from app.models.auth import Session as LoginSession

    login_session = await session.get(LoginSession, claims.session_id)
    if login_session is None or login_session.revoked_at is not None:
        raise UnauthorizedError("Session has been revoked.")

    user = await session.get(User, claims.subject)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise UnauthorizedError("User account is not active.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(permission: str):  # type: ignore[no-untyped-def]
    """Return a dependency enforcing ``permission`` on the path organization.

    The route must expose an ``organization_id`` path parameter. Superusers
    bypass the check.
    """

    async def _dependency(
        request: Request, user: CurrentUser, session: DbSession
    ) -> User:
        if user.is_superuser:
            return user
        raw_org_id = request.path_params.get("organization_id")
        if raw_org_id is None:
            raise ForbiddenError("Organization context is required.")
        organization_id = uuid.UUID(str(raw_org_id))
        await RBACService(session).require_permission(
            user.id, organization_id, permission
        )
        return user

    return _dependency
