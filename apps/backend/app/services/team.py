"""Team service."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import ConflictError, NotFoundError
from app.models.enums import AuditAction, SystemRole
from app.models.team import Team, TeamMember
from app.repositories.rbac import RoleRepository
from app.repositories.team import TeamMemberRepository, TeamRepository
from app.services.audit import AuditService
from app.utils.slug import slugify, unique_suffix


class TeamService:
    """Creates teams and manages team membership."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.teams = TeamRepository(session)
        self.members = TeamMemberRepository(session)
        self.roles = RoleRepository(session)
        self.audit = AuditService(session)

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        name: str,
        creator_id: uuid.UUID,
        slug: str | None = None,
        description: str | None = None,
    ) -> Team:
        """Create a team and add the creator as a manager-role member."""
        slug = slug or slugify(name)
        existing = await self.teams.list_for_org(organization_id)
        if any(t.slug == slug for t in existing):
            slug = f"{slug}-{unique_suffix()}"

        team = Team(
            organization_id=organization_id,
            name=name,
            slug=slug,
            description=description,
        )
        await self.teams.add(team)

        manager_role = await self.roles.get_org_role(
            organization_id, SystemRole.MANAGER.value
        )
        if manager_role is None:
            raise NotFoundError("Organization roles are not provisioned.")
        await self.members.add(
            TeamMember(team_id=team.id, user_id=creator_id, role_id=manager_role.id)
        )
        await self.audit.record(
            AuditAction.TEAM_CREATED,
            actor_id=creator_id,
            organization_id=organization_id,
            target_id=str(team.id),
        )
        return team

    async def list_for_org(self, organization_id: uuid.UUID) -> list[Team]:
        return await self.teams.list_for_org(organization_id)

    async def add_member(
        self, *, team_id: uuid.UUID, user_id: uuid.UUID, role_id: uuid.UUID
    ) -> TeamMember:
        if await self.members.get_membership(team_id, user_id) is not None:
            raise ConflictError("User is already a member of this team.")
        return await self.members.add(
            TeamMember(team_id=team_id, user_id=user_id, role_id=role_id)
        )
