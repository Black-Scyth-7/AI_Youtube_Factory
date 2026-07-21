"""Shared pytest fixtures for the backend test suite."""

from __future__ import annotations

import os
from collections.abc import Iterator

# Ensure tests run with a deterministic, self-contained environment before the
# application settings are imported anywhere.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_JSON", "false")

import pytest
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def app() -> Iterator[object]:
    """Provide the FastAPI application instance for the test session."""
    yield create_app()


@pytest.fixture()
def client(app: object) -> Iterator[TestClient]:
    """Provide a synchronous test client bound to the app lifespan."""
    with TestClient(app) as test_client:  # type: ignore[arg-type]
        yield test_client
