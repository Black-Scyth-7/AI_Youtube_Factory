"""Session management routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.dependencies.auth import CurrentUser, DbSession
from app.schemas.organization import SessionResponse
from app.services.session_service import SessionService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionResponse])
async def list_sessions(user: CurrentUser, session: DbSession) -> list[SessionResponse]:
    """List the current user's active login sessions."""
    active = await SessionService(session).list_active(user.id)
    return [SessionResponse.model_validate(s) for s in active]


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def terminate_session(
    session_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> None:
    """Terminate a specific session."""
    await SessionService(session).terminate(user_id=user.id, session_id=session_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def terminate_all_sessions(user: CurrentUser, session: DbSession) -> None:
    """Terminate all of the current user's sessions."""
    await SessionService(session).terminate_all(user.id)
