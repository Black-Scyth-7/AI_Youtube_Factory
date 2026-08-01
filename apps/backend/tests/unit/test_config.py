"""Tests for configuration loading and provider factories."""

from __future__ import annotations

import pytest
from app.config import Environment, Settings
from app.core.llm import LLMProvider, create_llm_client
from app.core.storage import StorageProvider, create_storage_client
from app.exceptions import ServiceUnavailableError
from pydantic import ValidationError


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


# -- Production secret hardening ----------------------------------------------
def _production_env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    """Point Settings at a production environment with explicit secrets."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    for name in ("SECRET_KEY", "JWT_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    for key, value in overrides.items():
        monkeypatch.setenv(key, value)


def test_production_refuses_placeholder_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """The hole: a deployment that forgot to set them signed tokens with a value
    published in this repository."""
    _production_env(monkeypatch)
    with pytest.raises(ValidationError, match="placeholder"):
        Settings()


def test_production_refuses_short_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    _production_env(monkeypatch, SECRET_KEY="abcdefgh", JWT_SECRET_KEY="abcdefgh")
    with pytest.raises(ValidationError, match="characters"):
        Settings()


def test_production_flags_either_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting one properly must not excuse the other."""
    _production_env(monkeypatch, SECRET_KEY="x" * 48)
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings()


def test_production_accepts_strong_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    _production_env(monkeypatch, SECRET_KEY="x" * 48, JWT_SECRET_KEY="y" * 48)
    settings = Settings()
    assert settings.is_production is True


@pytest.mark.parametrize("environment", ["local", "development", "staging", "test"])
def test_non_production_still_boots_with_defaults(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    """Local development must not need a generated secret."""
    monkeypatch.setenv("ENVIRONMENT", environment)
    for name in ("SECRET_KEY", "JWT_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert Settings().is_production is False
