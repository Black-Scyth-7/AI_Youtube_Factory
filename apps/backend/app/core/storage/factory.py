"""Storage provider factory.

Single entry point for obtaining a storage client. Providers register their
constructors here as they are implemented (later phases).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.storage.interfaces import StorageProvider
from app.exceptions.base import ServiceUnavailableError

_REGISTRY: dict[StorageProvider, Callable[[], Any]] = {}


def register_storage(provider: StorageProvider, factory: Callable[[], Any]) -> None:
    """Register a constructor for ``provider``."""
    _REGISTRY[provider] = factory


def create_storage_client(provider: StorageProvider) -> Any:
    """Instantiate the client for ``provider``.

    Raises:
        ServiceUnavailableError: If no implementation is registered yet.
    """
    factory = _REGISTRY.get(provider)
    if factory is None:
        raise ServiceUnavailableError(
            f"Storage provider '{provider}' is not implemented yet.",
            details={"provider": provider.value, "available": list(_REGISTRY)},
        )
    return factory()
