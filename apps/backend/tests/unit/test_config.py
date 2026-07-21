"""Tests for configuration loading and provider factories."""

from __future__ import annotations

import pytest
from app.config import Environment, Settings
from app.core.llm import LLMProvider, create_llm_client
from app.core.storage import StorageProvider, create_storage_client
from app.exceptions import ServiceUnavailableError


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.environment in set(Environment)
    assert settings.api_v1_prefix == "/api/v1"


def test_cors_origins_accepts_comma_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://a.com, http://b.com")
    settings = Settings()
    assert settings.cors_origins == ["http://a.com", "http://b.com"]


def test_sync_database_url_uses_psycopg() -> None:
    settings = Settings()
    assert "+psycopg" in settings.sync_database_url
    assert "+asyncpg" not in settings.sync_database_url


def test_unregistered_llm_provider_raises() -> None:
    with pytest.raises(ServiceUnavailableError):
        create_llm_client(LLMProvider.ANTHROPIC)


def test_unregistered_storage_provider_raises() -> None:
    with pytest.raises(ServiceUnavailableError):
        create_storage_client(StorageProvider.S3)
