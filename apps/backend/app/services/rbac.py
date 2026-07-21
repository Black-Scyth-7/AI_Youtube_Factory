"""RBAC service: permission seeding, role provisioning, and access checks."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import ForbiddenError
from app.models.enums import SystemRole
from app.models.organization import OrganizationMember
from app.models.rbac import Permission, Role
from app.repositories.rbac import PermissionRepository, RoleRepository
from app.security.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSIONS,
    ROLE_DISPLAY,
)


class RBACService:
    """Manages permissions, roles, and permission checks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.permissions = PermissionRepository(session)
        self.roles = RoleRepository(session)

    async def ensure_permissions(self) -> dict[str, Permission]:
        """Idempotently seed the global permission catalog; return by slug."""
        existing = {p.slug: p for p in await self.permissions.list_all(limit=1000)}
        for slug, description in PERMISSIONS.items():
            if slug not in existing:
                perm = Permission(slug=slug, description=description)
                self.session.add(perm)
                existing[slug] = perm
        await self.session.flush()
        return existing

    async def provision_system_roles(
        self, organization_id: uuid.UUID
    ) -> dict[SystemRole, Role]:
        """Create the built-in roles for an organization with their permissions."""
        catalog = await self.ensure_permissions()
        roles: dict[SystemRole, Role] = {}
        for system_role, slugs in DEFAULT_ROLE_PERMISSIONS.items():
            role = Role(
                slug=system_role.value,
                name=ROLE_DISPLAY[system_role],
                is_system=True,
                organization_id=organization_id,
                permissions=[catalog[s] for s in slugs],
            )
            self.session.add(role)
            roles[system_role] = role
        await self.session.flush()
        return roles

    async def get_permissions_for_user(
        self, user_id: uuid.UUID, organization_id: uuid.UUID
    ) -> set[str]:
        """Return the set of permission slugs a user has in an organization."""
        result = await self.session.execute(
            select(Role)
            .join(OrganizationMember, OrganizationMember.role_id == Role.id)
            .where(
                OrganizationMember.user_id == user_id,
                OrganizationMember.organization_id == organization_id,
                OrganizationMember.deleted_at.is_(None),
            )
        )
        role = result.scalars().first()
        if role is None:
            return set()
        loaded = await self.roles.get_with_permissions(role.id)
        return {p.slug for p in loaded.permissions} if loaded else set()

    async def require_permission(
        self, user_id: uuid.UUID, organization_id: uuid.UUID, permission: str
    ) -> None:
        """Raise :class:`ForbiddenError` if the user lacks ``permission``."""
        granted = await self.get_permissions_for_user(user_id, organization_id)
        if permission not in granted:
            raise ForbiddenError(
                "You do not have permission to perform this action.",
                details={"required": permission},
            )
