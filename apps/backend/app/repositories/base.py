"""Generic async repository base.

Encapsulates common data-access patterns (get by id, list, add, delete) so
concrete repositories stay focused on entity-specific queries. All access goes
through an injected :class:`AsyncSession`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base


class BaseRepository[ModelT: Base]:
    """Async CRUD helper bound to a single model type."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        """Return the entity by primary key, or ``None``."""
        return await self.session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        """Stage a new entity and flush to assign defaults/ids."""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Delete an entity."""
        await self.session.delete(entity)
        await self.session.flush()

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        """Return a page of entities."""
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
