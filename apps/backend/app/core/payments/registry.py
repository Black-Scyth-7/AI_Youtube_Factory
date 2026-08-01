"""Payment provider registry.

Mirrors the pipeline registry: providers register under a slug and billing
resolves them by configuration. The mock is always registered, so billing works
out of the box and no test needs a key.
"""

from __future__ import annotations

from collections.abc import Callable

from app.config import settings
from app.core.payments.interfaces import PaymentProvider
from app.core.payments.mock import MockPaymentProvider
from app.exceptions.base import ServiceUnavailableError

_REGISTRY: dict[str, Callable[[], PaymentProvider]] = {}


def register_provider(slug: str, factory: Callable[[], PaymentProvider]) -> None:
    """Register ``factory`` as the implementation for ``slug``."""
    _REGISTRY[slug] = factory


def get_provider(slug: str | None = None) -> PaymentProvider:
    """Resolve a provider, falling back to the configured default."""
    resolved = slug or settings.payment_provider
    factory = _REGISTRY.get(resolved)
    if factory is None:
        raise ServiceUnavailableError(
            f"No payment provider registered for '{resolved}'.",
            details={"requested": resolved, "available": sorted(_REGISTRY)},
        )
    return factory()


def available_providers() -> list[str]:
    return sorted(_REGISTRY)


def reset_providers() -> None:
    """Drop every registration and restore the built-in mock (tests)."""
    _REGISTRY.clear()
    register_provider("mock", MockPaymentProvider)


register_provider("mock", MockPaymentProvider)
