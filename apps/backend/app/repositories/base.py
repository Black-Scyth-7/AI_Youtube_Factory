"""Generic async repository base.

Encapsulates common data-access patterns — CRUD, pagination, filtering,
sorting, soft delete, and bulk operations — so concrete repositories stay focused
on entity-specific queries and contain **no business logic**. All access goes
through an injected :class:`AsyncSession`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.pagination import FilterSpec, Page, PageParams, SortParam
from app.models.base import Base

_OPERATORS = {"eq", "ne", "gt", "ge", "lt", "le", "like", "ilike", "in"}


class BaseRepository[ModelT: Base]:
    """Async CRUD + query helper bound to a single model type."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -- Basic CRUD -------------------------------------------------------
    async def get(self, entity_id: uuid.UUID) -> ModelT | None:
        """Return the entity by primary key, or ``None``."""
        return await self.session.get(self.model, entity_id)

    async def add(self, entity: ModelT) -> ModelT:
        """Stage a new entity and flush to assign defaults/ids."""
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Hard-delete an entity."""
        await self.session.delete(entity)
        await self.session.flush()

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        """Return a page of entities (legacy helper)."""
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    # -- Soft delete ------------------------------------------------------
    async def soft_delete(self, entity: ModelT) -> None:
        """Mark an entity as soft-deleted (requires a ``deleted_at`` column)."""
        if not hasattr(entity, "deleted_at"):
            raise AttributeError(f"{self.model.__name__} does not support soft delete.")
        entity.deleted_at = datetime.now(UTC)
        await self.session.flush()

    async def restore(self, entity: ModelT) -> None:
        """Clear a soft-delete marker."""
        entity.deleted_at = None  # type: ignore[attr-defined]
        await self.session.flush()

    # -- Bulk operations --------------------------------------------------
    async def bulk_add(self, entities: list[ModelT]) -> list[ModelT]:
        """Add many entities in one flush."""
        self.session.add_all(entities)
        await self.session.flush()
        return entities

    # -- Query building ---------------------------------------------------
    def _base_query(self, *, include_deleted: bool = False) -> Select[tuple[ModelT]]:
        stmt = select(self.model)
        if not include_deleted and hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return stmt

    def _apply_filters(
        self, stmt: Select[tuple[ModelT]], filters: list[FilterSpec]
    ) -> Select[tuple[ModelT]]:
        for f in filters:
            column = getattr(self.model, f.field, None)
            if column is None or f.op not in _OPERATORS:
                raise ValueError(f"Invalid filter: {f.field} {f.op}")
            if f.op == "in":
                stmt = stmt.where(column.in_(f.value))
            elif f.op in {"like", "ilike"}:
                stmt = stmt.where(getattr(column, f.op)(f"%{f.value}%"))
            else:
                stmt = stmt.where(getattr(column, f"__{f.op}__")(f.value))
        return stmt

    def _apply_sort(
        self, stmt: Select[tuple[ModelT]], sort: list[SortParam]
    ) -> Select[tuple[ModelT]]:
        for s in sort:
            column = getattr(self.model, s.field, None)
            if column is None:
                raise ValueError(f"Invalid sort field: {s.field}")
            stmt = stmt.order_by(column.desc() if s.descending else column.asc())
        return stmt

    async def count(
        self,
        *,
        filters: list[FilterSpec] | None = None,
        include_deleted: bool = False,
    ) -> int:
        """Count matching rows."""
        stmt = self._base_query(include_deleted=include_deleted)
        if filters:
            stmt = self._apply_filters(stmt, filters)
        result = await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )
        return int(result.scalar_one())

    async def paginate(
        self,
        params: PageParams,
        *,
        filters: list[FilterSpec] | None = None,
        sort: list[SortParam] | None = None,
        include_deleted: bool = False,
    ) -> Page[ModelT]:
        """Return a filtered, sorted, paginated page of entities."""
        filters = filters or []
        total = await self.count(filters=filters, include_deleted=include_deleted)

        stmt = self._base_query(include_deleted=include_deleted)
        stmt = self._apply_filters(stmt, filters)
        stmt = self._apply_sort(stmt, sort or [SortParam("created_at", descending=True)])
        stmt = stmt.limit(params.limit).offset(params.offset)

        result = await self.session.execute(stmt)
        return Page(
            items=list(result.scalars().all()),
            total=total,
            page=params.page,
            size=params.limit,
        )

    async def find_by(self, **fields: Any) -> ModelT | None:
        """Return the first entity matching all ``fields`` (excludes deleted)."""
        stmt = self._base_query()
        for key, value in fields.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none()

    async def exists(self, **fields: Any) -> bool:
        return (await self.find_by(**fields)) is not None
