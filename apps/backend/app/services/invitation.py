"""Invitation service."""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.models.enums import AuditAction, InvitationStatus
from app.models.invitation import Invitation
from app.repositories.invitation import InvitationRepository
from app.repositories.rbac import RoleRepository
from app.security.tokens import generate_token, hash_token
from app.services.audit import AuditService
from app.services.email import EmailService
from app.services.organization import OrganizationService


class InvitationService:
    """Creates, revokes, and accepts organization invitations."""

    def __init__(
        self, session: AsyncSession, *, email_service: EmailService | None = None
    ) -> None:
        self.session = session
        self.repo = InvitationRepository(session)
        self.roles = RoleRepository(session)
        self.orgs = OrganizationService(session)
        self.audit = AuditService(session)
        self.email = email_service or EmailService()

    async def invite(
        self,
        *,
        organization_id: uuid.UUID,
        email: str,
        role_slug: str,
        invited_by_id: uuid.UUID,
        org_name: str,
    ) -> tuple[Invitation, str]:
        """Create an invitation and email it; returns the record and raw token."""
        role = await self.roles.get_org_role(organization_id, role_slug)
        if role is None:
            raise NotFoundError(f"Role '{role_slug}' not found.")
        raw = generate_token()
        invitation = Invitation(
            organization_id=organization_id,
            email=email.lower(),
            role_id=role.id,
            invited_by_id=invited_by_id,
            token_hash=hash_token(raw),
            status=InvitationStatus.PENDING.value,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.invitation_expire_days),
        )
        await self.repo.add(invitation)
        await self.email.send_invitation(to=email, token=raw, org_name=org_name)
        await self.audit.record(
            AuditAction.INVITE_SENT,
            actor_id=invited_by_id,
            organization_id=organization_id,
            target_id=str(invitation.id),
        )
        return invitation, raw

    async def list_for_org(self, organization_id: uuid.UUID) -> list[Invitation]:
        return await self.repo.list_for_org(organization_id)

    async def revoke(self, *, invitation_id: uuid.UUID, actor_id: uuid.UUID) -> None:
        invitation = await self.repo.get(invitation_id)
        if invitation is None or invitation.deleted_at is not None:
            raise NotFoundError("Invitation not found.")
        invitation.status = InvitationStatus.REVOKED.value
        await self.session.flush()
        await self.audit.record(
            AuditAction.INVITE_REVOKED,
            actor_id=actor_id,
            organization_id=invitation.organization_id,
            target_id=str(invitation.id),
        )

    async def accept(self, *, token: str, user_id: uuid.UUID) -> Invitation:
        """Accept an invitation and add the user to the organization."""
        invitation = await self.repo.get_by_hash(hash_token(token))
        if invitation is None or invitation.status != InvitationStatus.PENDING.value:
            raise ValidationError("Invalid or already-processed invitation.")
        reference = (
            invitation.expires_at
            if invitation.expires_at.tzinfo
            else invitation.expires_at.replace(tzinfo=UTC)
        )
        if reference < datetime.now(UTC):
            invitation.status = InvitationStatus.EXPIRED.value
            await self.session.flush()
            raise ValidationError("Invitation has expired.")

        role = await self.roles.get(invitation.role_id)
        if role is None:
            raise NotFoundError("Invitation role no longer exists.")
        # Accepting is idempotent — a user who is already a member is fine.
        with contextlib.suppress(ConflictError):
            await self.orgs.add_member(
                organization_id=invitation.organization_id,
                user_id=user_id,
                role_slug=role.slug,
            )

        invitation.status = InvitationStatus.ACCEPTED.value
        invitation.accepted_at = datetime.now(UTC)
        await self.session.flush()
        await self.audit.record(
            AuditAction.INVITE_ACCEPTED,
            actor_id=user_id,
            organization_id=invitation.organization_id,
            target_id=str(invitation.id),
        )
        return invitation
