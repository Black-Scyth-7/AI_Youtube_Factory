"""Organization and membership repositories."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.organization import Organization, OrganizationMember
from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[Organization]):
    """Data access for :class:`Organization`."""

    model = Organization

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self.session.execute(
            select(Organization).where(
                Organization.slug == slug, Organization.deleted_at.is_(None)
            )
        )
        return result.scalar_one_or_none()

    async def slug_exists(self, slug: str) -> bool:
        return (await self.get_by_slug(slug)) is not None


class OrganizationMemberRepository(BaseRepository[OrganizationMember]):
    """Data access for :class:`OrganizationMember`."""

    model = OrganizationMember

    async def get_membership(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> OrganizationMember | None:
        result = await self.session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.user_id == user_id,
                OrganizationMember.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[OrganizationMember]:
        result = await self.session.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def list_for_org(self, organization_id: uuid.UUID) -> list[OrganizationMember]:
        result = await self.session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())
