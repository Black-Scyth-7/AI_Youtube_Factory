"""API key repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.api_key import ApiKey
from app.repositories.base import BaseRepository


class ApiKeyRepository(BaseRepository[ApiKey]):
    """Data access for :class:`ApiKey`."""

    model = ApiKey

    async def get_by_prefix(self, prefix: str) -> ApiKey | None:
        result = await self.session.execute(select(ApiKey).where(ApiKey.prefix == prefix))
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[ApiKey]:
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.user_id == user_id, ApiKey.deleted_at.is_(None))
        )
        return list(result.scalars().all())
