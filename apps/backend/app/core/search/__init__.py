"""Search abstraction.

Provides a provider-neutral search interface plus a PostgreSQL/SQL ``ILIKE``
implementation for now. A future ElasticSearch/OpenSearch provider plugs in
behind :class:`SearchProvider` without changing call sites.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import Select, or_
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(slots=True, frozen=True)
class SearchQuery:
    """A search request."""

    text: str
    fields: list[str]
    limit: int = 20
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SearchHit:
    """A single search result with a relevance score."""

    id: str
    score: float
    highlights: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class SearchProvider(Protocol):
    """Executes a search query and returns ranked hits."""

    async def search(self, query: SearchQuery) -> list[SearchHit]: ...


class SqlTextSearch:
    """Simple full-text-ish search over a model using SQL ``ILIKE``."""

    def __init__(self, session: AsyncSession, model: type[Any]) -> None:
        self.session = session
        self.model = model

    def build_statement(self, query: SearchQuery) -> Select[tuple[Any]]:
        """Build a SELECT applying an OR of ILIKE clauses across fields."""
        from sqlalchemy import select

        stmt = select(self.model)
        if hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))
        clauses = []
        for field_name in query.fields:
            column = getattr(self.model, field_name, None)
            if column is not None:
                clauses.append(column.ilike(f"%{query.text}%"))
        if clauses:
            stmt = stmt.where(or_(*clauses))
        for key, value in query.filters.items():
            column = getattr(self.model, key, None)
            if column is not None:
                stmt = stmt.where(column == value)
        return stmt.limit(query.limit)

    async def search(self, query: SearchQuery) -> list[Any]:
        """Return matching model rows (ranking/highlighting to come)."""
        result = await self.session.execute(self.build_statement(query))
        return list(result.scalars().all())


__all__ = [
    "SearchHit",
    "SearchProvider",
    "SearchQuery",
    "SqlTextSearch",
]
