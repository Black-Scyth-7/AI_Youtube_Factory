"""Organization, membership, and team routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import CurrentUser, DbSession, require_permission
from app.models.user import User
from app.schemas.organization import (
    MembershipResponse,
    OrganizationCreateRequest,
    OrganizationResponse,
    TeamCreateRequest,
    TeamResponse,
    UpdateMemberRoleRequest,
)
from app.services.organization import OrganizationService
from app.services.team import TeamService

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    body: OrganizationCreateRequest, user: CurrentUser, session: DbSession
) -> OrganizationResponse:
    """Create an organization owned by the current user."""
    org = await OrganizationService(session).create(
        name=body.name, owner_id=user.id, slug=body.slug
    )
    return OrganizationResponse.model_validate(org)


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    user: CurrentUser, session: DbSession
) -> list[OrganizationResponse]:
    """List organizations the current user belongs to."""
    orgs = await OrganizationService(session).list_for_user(user.id)
    return [OrganizationResponse.model_validate(o) for o in orgs]


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: uuid.UUID,
    session: DbSession,
    _: User = Depends(require_permission("analytics.read")),
) -> OrganizationResponse:
    """Get a single organization (requires membership)."""
    org = await OrganizationService(session).get_or_404(organization_id)
    return OrganizationResponse.model_validate(org)


@router.get("/{organization_id}/members", response_model=list[MembershipResponse])
async def list_members(
    organization_id: uuid.UUID,
    session: DbSession,
    _: User = Depends(require_permission("member.manage")),
) -> list[MembershipResponse]:
    """List members of an organization."""
    members = await OrganizationService(session).members.list_for_org(organization_id)
    return [MembershipResponse.model_validate(m) for m in members]


@router.patch("/{organization_id}/members/{user_id}", response_model=MembershipResponse)
async def update_member_role(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    session: DbSession,
    _: User = Depends(require_permission("member.manage")),
) -> MembershipResponse:
    """Change a member's role."""
    member = await OrganizationService(session).update_member_role(
        organization_id=organization_id, user_id=user_id, role_slug=body.role_slug
    )
    return MembershipResponse.model_validate(member)


@router.post(
    "/{organization_id}/teams",
    response_model=TeamResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_team(
    organization_id: uuid.UUID,
    body: TeamCreateRequest,
    user: CurrentUser,
    session: DbSession,
    _: User = Depends(require_permission("team.manage")),
) -> TeamResponse:
    """Create a team within an organization."""
    team = await TeamService(session).create(
        organization_id=organization_id,
        name=body.name,
        creator_id=user.id,
        slug=body.slug,
        description=body.description,
    )
    return TeamResponse.model_validate(team)


@router.get("/{organization_id}/teams", response_model=list[TeamResponse])
async def list_teams(
    organization_id: uuid.UUID,
    session: DbSession,
    _: User = Depends(require_permission("analytics.read")),
) -> list[TeamResponse]:
    """List teams within an organization."""
    teams = await TeamService(session).list_for_org(organization_id)
    return [TeamResponse.model_validate(t) for t in teams]
