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


def test_unregistered_storage_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """The factory must reject a provider with no registered implementation.

    This used to assert that against S3, which is now implemented. The behaviour
    still matters for any provider added to the enum before its factory, so it is
    exercised by unregistering one for the duration of the test.
    """
    from app.core.storage import factory

    registry = dict(factory._REGISTRY)
    monkeypatch.setattr(factory, "_REGISTRY", registry)
    registry.pop(StorageProvider.S3)

    with pytest.raises(ServiceUnavailableError):
        create_storage_client(StorageProvider.S3)


def test_every_storage_provider_is_registered() -> None:
    """Counterpart to the above: nothing in the enum may be left unimplemented."""
    for provider in StorageProvider:
        assert create_storage_client(provider) is not None
