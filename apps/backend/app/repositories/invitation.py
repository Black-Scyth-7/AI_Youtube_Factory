"""Invitation and audit-log repositories."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.invitation import Invitation
from app.repositories.base import BaseRepository


class InvitationRepository(BaseRepository[Invitation]):
    """Data access for :class:`Invitation`."""

    model = Invitation

    async def get_by_hash(self, token_hash: str) -> Invitation | None:
        result = await self.session.execute(
            select(Invitation).where(Invitation.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def list_for_org(self, organization_id: uuid.UUID) -> list[Invitation]:
        result = await self.session.execute(
            select(Invitation).where(
                Invitation.organization_id == organization_id,
                Invitation.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())


class AuditLogRepository(BaseRepository[AuditLog]):
    """Data access for :class:`AuditLog` (append-only)."""

    model = AuditLog

    async def list_for_org(
        self, organization_id: uuid.UUID, limit: int = 100
    ) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.organization_id == organization_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
