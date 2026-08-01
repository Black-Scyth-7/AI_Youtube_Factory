"""Pipeline provider registry.

Mirrors the LLM registry: providers register a factory under a slug and the
pipeline resolves them by configuration. The mock is always registered, so the
pipeline works out of the box and CI never needs a credential.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.config import settings
from app.core.pipeline.interfaces import ProviderKind
from app.core.pipeline.mock import (
    MockAnalyticsProvider,
    MockPublishProvider,
    MockRenderProvider,
    MockSpeechProvider,
)
from app.exceptions.base import ServiceUnavailableError

_REGISTRY: dict[tuple[ProviderKind, str], Callable[[], Any]] = {}


def register_provider(kind: ProviderKind, slug: str, factory: Callable[[], Any]) -> None:
    """Register ``factory`` as the ``slug`` implementation of ``kind``."""
    _REGISTRY[(kind, slug)] = factory


def get_provider(kind: ProviderKind, slug: str | None = None) -> Any:
    """Resolve a provider, falling back to the configured default."""
    resolved = slug or _configured_slug(kind)
    factory = _REGISTRY.get((kind, resolved))
    if factory is None:
        raise ServiceUnavailableError(
            f"No {kind.value} provider registered for '{resolved}'.",
            details={
                "kind": kind.value,
                "requested": resolved,
                "available": sorted(s for k, s in _REGISTRY if k == kind),
            },
        )
    return factory()


def _configured_slug(kind: ProviderKind) -> str:
    return {
        ProviderKind.SPEECH: settings.pipeline_speech_provider,
        ProviderKind.RENDER: settings.pipeline_render_provider,
        ProviderKind.PUBLISH: settings.pipeline_publish_provider,
        ProviderKind.ANALYTICS: settings.pipeline_analytics_provider,
    }[kind]


def available_providers(kind: ProviderKind) -> list[str]:
    return sorted(slug for registered, slug in _REGISTRY if registered == kind)


def reset_providers() -> None:
    """Drop every registration and restore the built-in mocks (tests)."""
    _REGISTRY.clear()
    _register_mocks()


def _register_mocks() -> None:
    register_provider(ProviderKind.SPEECH, "mock", MockSpeechProvider)
    register_provider(ProviderKind.RENDER, "mock", MockRenderProvider)
    register_provider(ProviderKind.PUBLISH, "mock", MockPublishProvider)
    register_provider(ProviderKind.ANALYTICS, "mock", MockAnalyticsProvider)


_register_mocks()
