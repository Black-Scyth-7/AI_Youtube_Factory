"""Invitation routes (organization-scoped creation + acceptance)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import CurrentUser, DbSession, require_permission
from app.models.user import User
from app.schemas.organization import (
    AcceptInvitationRequest,
    InvitationCreateRequest,
    InvitationResponse,
)
from app.services.invitation import InvitationService
from app.services.organization import OrganizationService

router = APIRouter(tags=["invitations"])


@router.post(
    "/organizations/{organization_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    organization_id: uuid.UUID,
    body: InvitationCreateRequest,
    user: CurrentUser,
    session: DbSession,
    _: User = Depends(require_permission("member.manage")),
) -> InvitationResponse:
    """Invite a user (by email) to join the organization."""
    org = await OrganizationService(session).get_or_404(organization_id)
    invitation, _raw = await InvitationService(session).invite(
        organization_id=organization_id,
        email=body.email,
        role_slug=body.role_slug,
        invited_by_id=user.id,
        org_name=org.name,
    )
    return InvitationResponse.model_validate(invitation)


@router.get(
    "/organizations/{organization_id}/invitations",
    response_model=list[InvitationResponse],
)
async def list_invitations(
    organization_id: uuid.UUID,
    session: DbSession,
    _: User = Depends(require_permission("member.manage")),
) -> list[InvitationResponse]:
    """List invitations for an organization."""
    invitations = await InvitationService(session).list_for_org(organization_id)
    return [InvitationResponse.model_validate(i) for i in invitations]


@router.delete(
    "/organizations/{organization_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_invitation(
    organization_id: uuid.UUID,
    invitation_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    _: User = Depends(require_permission("member.manage")),
) -> None:
    """Revoke a pending invitation."""
    await InvitationService(session).revoke(invitation_id=invitation_id, actor_id=user.id)


@router.post("/invitations/accept", response_model=InvitationResponse)
async def accept_invitation(
    body: AcceptInvitationRequest, user: CurrentUser, session: DbSession
) -> InvitationResponse:
    """Accept an invitation and join the organization."""
    invitation = await InvitationService(session).accept(
        token=body.token, user_id=user.id
    )
    return InvitationResponse.model_validate(invitation)
