"""Team and team-membership repositories."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.team import Team, TeamMember
from app.repositories.base import BaseRepository


class TeamRepository(BaseRepository[Team]):
    """Data access for :class:`Team`."""

    model = Team

    async def list_for_org(self, organization_id: uuid.UUID) -> list[Team]:
        result = await self.session.execute(
            select(Team).where(
                Team.organization_id == organization_id, Team.deleted_at.is_(None)
            )
        )
        return list(result.scalars().all())


class TeamMemberRepository(BaseRepository[TeamMember]):
    """Data access for :class:`TeamMember`."""

    model = TeamMember

    async def get_membership(
        self, team_id: uuid.UUID, user_id: uuid.UUID
    ) -> TeamMember | None:
        result = await self.session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
                TeamMember.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_team(self, team_id: uuid.UUID) -> list[TeamMember]:
        result = await self.session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id, TeamMember.deleted_at.is_(None)
            )
        )
        return list(result.scalars().all())
