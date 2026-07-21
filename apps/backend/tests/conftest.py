"""Shared pytest fixtures for the backend test suite."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

# Deterministic, self-contained environment before settings import anywhere.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest
import pytest_asyncio
from app.db.session import session_scope
from app.dependencies.db import get_db_session
from app.main import create_app
from app.models.base import Base
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture(scope="session")
def app() -> Iterator[object]:
    """Provide the FastAPI application instance for the test session."""
    yield create_app()


@pytest.fixture()
def client(app: object) -> Iterator[TestClient]:
    """Synchronous client for endpoints that don't require the database."""
    with TestClient(app) as test_client:  # type: ignore[arg-type]
        yield test_client


@pytest_asyncio.fixture()
async def db_sessionmaker() -> AsyncIterator[async_sessionmaker]:
    """A fresh in-memory SQLite database with all tables created."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture()
async def api(
    app: object, db_sessionmaker: async_sessionmaker
) -> AsyncIterator[AsyncClient]:
    """Async HTTP client bound to the app with the test database injected."""

    async def _override() -> AsyncIterator[object]:
        async with session_scope(db_sessionmaker) as session:
            yield session

    app.dependency_overrides[get_db_session] = _override  # type: ignore[attr-defined]
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()  # type: ignore[attr-defined]


@pytest_asyncio.fixture()
async def session(db_sessionmaker: async_sessionmaker) -> AsyncIterator[object]:
    """A direct DB session for service-level tests."""
    async with session_scope(db_sessionmaker) as s:
        yield s
