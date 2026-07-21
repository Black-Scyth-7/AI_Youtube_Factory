"""Organization service."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import ConflictError, NotFoundError
from app.models.enums import SystemRole
from app.models.organization import Organization, OrganizationMember
from app.repositories.organization import (
    OrganizationMemberRepository,
    OrganizationRepository,
)
from app.services.rbac import RBACService
from app.utils.slug import slugify, unique_suffix


class OrganizationService:
    """Creates and manages organizations and memberships."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.orgs = OrganizationRepository(session)
        self.members = OrganizationMemberRepository(session)
        self.rbac = RBACService(session)

    async def create(
        self, *, name: str, owner_id: uuid.UUID, slug: str | None = None
    ) -> Organization:
        """Create an organization, seed system roles, and add the owner."""
        slug = slug or slugify(name)
        if await self.orgs.slug_exists(slug):
            slug = f"{slug}-{unique_suffix()}"

        org = Organization(name=name, slug=slug, owner_id=owner_id)
        await self.orgs.add(org)

        roles = await self.rbac.provision_system_roles(org.id)
        owner_role = roles[SystemRole.OWNER]
        await self.members.add(
            OrganizationMember(
                organization_id=org.id, user_id=owner_id, role_id=owner_role.id
            )
        )
        return org

    async def get_or_404(self, organization_id: uuid.UUID) -> Organization:
        org = await self.orgs.get(organization_id)
        if org is None or org.deleted_at is not None:
            raise NotFoundError("Organization not found.")
        return org

    async def list_for_user(self, user_id: uuid.UUID) -> list[Organization]:
        memberships = await self.members.list_for_user(user_id)
        orgs: list[Organization] = []
        for m in memberships:
            org = await self.orgs.get(m.organization_id)
            if org is not None and org.deleted_at is None:
                orgs.append(org)
        return orgs

    async def add_member(
        self, *, organization_id: uuid.UUID, user_id: uuid.UUID, role_slug: str
    ) -> OrganizationMember:
        """Add a user to an organization with the given role slug."""
        if await self.members.get_membership(organization_id, user_id) is not None:
            raise ConflictError("User is already a member of this organization.")
        role = await self.rbac.roles.get_org_role(organization_id, role_slug)
        if role is None:
            raise NotFoundError(f"Role '{role_slug}' not found.")
        return await self.members.add(
            OrganizationMember(
                organization_id=organization_id, user_id=user_id, role_id=role.id
            )
        )

    async def update_member_role(
        self, *, organization_id: uuid.UUID, user_id: uuid.UUID, role_slug: str
    ) -> OrganizationMember:
        member = await self.members.get_membership(organization_id, user_id)
        if member is None:
            raise NotFoundError("Membership not found.")
        role = await self.rbac.roles.get_org_role(organization_id, role_slug)
        if role is None:
            raise NotFoundError(f"Role '{role_slug}' not found.")
        member.role_id = role.id
        await self.session.flush()
        return member
