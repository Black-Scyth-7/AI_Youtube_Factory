"""Role and permission repositories."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.rbac import Permission, Role
from app.repositories.base import BaseRepository


class PermissionRepository(BaseRepository[Permission]):
    """Data access for :class:`Permission`."""

    model = Permission

    async def get_by_slug(self, slug: str) -> Permission | None:
        result = await self.session.execute(
            select(Permission).where(Permission.slug == slug)
        )
        return result.scalar_one_or_none()

    async def all_by_slugs(self, slugs: set[str]) -> list[Permission]:
        result = await self.session.execute(
            select(Permission).where(Permission.slug.in_(slugs))
        )
        return list(result.scalars().all())


class RoleRepository(BaseRepository[Role]):
    """Data access for :class:`Role`."""

    model = Role

    async def get_with_permissions(self, role_id: uuid.UUID) -> Role | None:
        result = await self.session.execute(
            select(Role).where(Role.id == role_id).options(selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def get_org_role(
        self, organization_id: uuid.UUID | None, slug: str
    ) -> Role | None:
        result = await self.session.execute(
            select(Role)
            .where(Role.organization_id == organization_id, Role.slug == slug)
            .options(selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, organization_id: uuid.UUID) -> list[Role]:
        result = await self.session.execute(
            select(Role)
            .where(Role.organization_id == organization_id)
            .options(selectinload(Role.permissions))
        )
        return list(result.scalars().all())
