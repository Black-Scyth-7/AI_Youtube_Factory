"""LLM provider factory.

Central place that maps a :class:`LLMProvider` to a concrete client. This is the
*only* module future application code touches to obtain an LLM client, so adding
a provider requires changes here and in the provider module — nowhere else.

Phase 01 ships the registry and a clear failure mode; concrete providers are
registered in Phase 04.
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.llm.base import BaseLLMClient
from app.core.llm.interfaces import LLMProvider
from app.exceptions.base import ServiceUnavailableError

# Provider constructors are registered here as they are implemented.
_REGISTRY: dict[LLMProvider, Callable[[], BaseLLMClient]] = {}


def register_provider(
    provider: LLMProvider, factory: Callable[[], BaseLLMClient]
) -> None:
    """Register a constructor for ``provider``."""
    _REGISTRY[provider] = factory


def create_llm_client(provider: LLMProvider) -> BaseLLMClient:
    """Instantiate the client for ``provider``.

    Raises:
        ServiceUnavailableError: If no implementation is registered yet.
    """
    factory = _REGISTRY.get(provider)
    if factory is None:
        raise ServiceUnavailableError(
            f"LLM provider '{provider}' is not implemented yet.",
            details={"provider": provider.value, "available": list(_REGISTRY)},
        )
    return factory()
