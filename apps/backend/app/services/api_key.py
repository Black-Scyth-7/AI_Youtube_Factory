"""API key service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import NotFoundError, UnauthorizedError
from app.models.api_key import ApiKey
from app.models.enums import AuditAction
from app.repositories.api_key import ApiKeyRepository
from app.security.tokens import generate_api_key, hash_token
from app.services.audit import AuditService


@dataclass(slots=True, frozen=True)
class CreatedApiKey:
    """A newly created API key plus its one-time raw value."""

    api_key: ApiKey
    raw_key: str


class ApiKeyService:
    """Creates, lists, verifies, and revokes API keys."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ApiKeyRepository(session)
        self.audit = AuditService(session)

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        scopes: list[str],
        expires_in_days: int | None = None,
        organization_id: uuid.UUID | None = None,
    ) -> CreatedApiKey:
        """Create an API key and return the raw value (shown once)."""
        raw_key, prefix, secret_hash = generate_api_key()
        expires_at = (
            datetime.now(UTC) + timedelta(days=expires_in_days)
            if expires_in_days
            else None
        )
        key = ApiKey(
            user_id=user_id,
            organization_id=organization_id,
            name=name,
            prefix=prefix,
            secret_hash=secret_hash,
            scopes=scopes,
            expires_at=expires_at,
        )
        await self.repo.add(key)
        await self.audit.record(
            AuditAction.API_KEY_CREATED, actor_id=user_id, target_id=str(key.id)
        )
        return CreatedApiKey(api_key=key, raw_key=raw_key)

    async def list_for_user(self, user_id: uuid.UUID) -> list[ApiKey]:
        return await self.repo.list_for_user(user_id)

    async def revoke(self, *, user_id: uuid.UUID, key_id: uuid.UUID) -> None:
        key = await self.repo.get(key_id)
        if key is None or key.user_id != user_id or key.deleted_at is not None:
            raise NotFoundError("API key not found.")
        key.revoked_at = datetime.now(UTC)
        await self.session.flush()
        await self.audit.record(
            AuditAction.API_KEY_REVOKED, actor_id=user_id, target_id=str(key.id)
        )

    async def authenticate(self, raw_key: str) -> ApiKey:
        """Validate a raw API key and return the record, updating last-used."""
        try:
            prefix, secret = raw_key.split(".", 1)
        except ValueError as exc:
            raise UnauthorizedError("Malformed API key.") from exc
        key = await self.repo.get_by_prefix(prefix)
        if key is None or key.revoked_at is not None or key.deleted_at is not None:
            raise UnauthorizedError("Invalid API key.")
        if key.expires_at is not None and _expired(key.expires_at):
            raise UnauthorizedError("API key has expired.")
        if hash_token(secret) != key.secret_hash:
            raise UnauthorizedError("Invalid API key.")
        key.last_used_at = datetime.now(UTC)
        await self.session.flush()
        return key


def _expired(expires_at: datetime) -> bool:
    reference = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
    return reference < datetime.now(UTC)
