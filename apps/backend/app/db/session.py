"""Async database engine and session management.

Creates the SQLAlchemy 2.0 async engine and session factory, and exposes an
``async with`` context manager for request-scoped sessions. Connection pooling
uses sane production defaults with pre-ping to recover from dropped connections.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Create the async SQLAlchemy engine from settings."""
    return create_async_engine(
        str(settings.database_url),
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        future=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to ``engine``."""
    return async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
        autoflush=False,
    )


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Provide a transactional session scope.

    Commits on success, rolls back on error, and always closes the session.
    """
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
