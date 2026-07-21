"""Database session dependency.

Provides a request-scoped, transactional :class:`AsyncSession`. The session
factory is created once from settings and reused; tests override
:func:`get_db_session` to bind an isolated engine.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import settings
from app.db.session import create_engine, create_session_factory, session_scope

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the cached session factory, creating it on first use."""
    global _engine, _factory
    if _factory is None:
        _engine = create_engine(settings)
        _factory = create_session_factory(_engine)
    return _factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a transactional session (commit on success, rollback on error)."""
    async with session_scope(get_session_factory()) as session:
        yield session
