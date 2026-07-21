"""Audit logging service."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.enums import AuditAction


class AuditService:
    """Records immutable audit-log entries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        action: AuditAction,
        *,
        actor_id: uuid.UUID | None = None,
        organization_id: uuid.UUID | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        ip_address: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Append an audit record and flush it."""
        entry = AuditLog(
            action=action.value,
            actor_id=actor_id,
            organization_id=organization_id,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip_address,
            metadata_json=metadata or {},
        )
        self.session.add(entry)
        await self.session.flush()
        return entry
