"""Provider registry.

Maps provider slugs to constructors and resolves the active provider. This is the
new Phase 04 registry (independent of the Phase 01 legacy factory). The mock
provider is always available; the Anthropic provider is registered too and used
when configured with an API key.
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.llm.base import BaseLLMProvider
from app.core.llm.exceptions import ProviderNotAvailableError
from app.core.llm.providers import AnthropicProvider, MockProvider

_REGISTRY: dict[str, Callable[[], BaseLLMProvider]] = {
    "anthropic": AnthropicProvider,
    "claude": AnthropicProvider,
    "mock": MockProvider,
}

_INSTANCES: dict[str, BaseLLMProvider] = {}


def register_provider(slug: str, factory: Callable[[], BaseLLMProvider]) -> None:
    """Register a provider constructor under ``slug``."""
    _REGISTRY[slug] = factory
    _INSTANCES.pop(slug, None)


def get_provider(slug: str) -> BaseLLMProvider:
    """Return a cached provider instance for ``slug``."""
    if slug not in _INSTANCES:
        factory = _REGISTRY.get(slug)
        if factory is None:
            raise ProviderNotAvailableError(
                f"No LLM provider registered for '{slug}'.",
                details={"available": sorted(_REGISTRY)},
            )
        _INSTANCES[slug] = factory()
    return _INSTANCES[slug]


def available_providers() -> list[str]:
    """Return the registered provider slugs."""
    return sorted(_REGISTRY)


def reset_providers() -> None:
    """Clear cached provider instances (used in tests)."""
    _INSTANCES.clear()
