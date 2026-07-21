"""High-level cache service.

Wraps a :class:`CacheBackend` with JSON serialization, namespaced keys, TTL
defaults, ``get_or_set`` cache-warming, and namespace invalidation. A module
singleton is provided via :func:`get_cache`, selecting Redis when available and
falling back to an in-process cache otherwise.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar, cast

from app.config import settings
from app.core.cache.backend import CacheBackend, InMemoryCache, RedisCache
from app.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

DEFAULT_TTL = 300
_KEY_SEP = ":"


class CacheService:
    """Namespaced, JSON-serialized cache over a pluggable backend."""

    def __init__(self, backend: CacheBackend, *, prefix: str = "ayf") -> None:
        self._backend = backend
        self._prefix = prefix

    def _key(self, namespace: str, key: str) -> str:
        return _KEY_SEP.join((self._prefix, namespace, key))

    async def get(self, namespace: str, key: str) -> Any | None:
        raw = await self._backend.get(self._key(namespace, key))
        return json.loads(raw) if raw is not None else None

    async def set(
        self, namespace: str, key: str, value: Any, ttl: int | None = DEFAULT_TTL
    ) -> None:
        await self._backend.set(
            self._key(namespace, key), json.dumps(value, default=str), ttl
        )

    async def delete(self, namespace: str, key: str) -> None:
        await self._backend.delete(self._key(namespace, key))

    async def invalidate_namespace(self, namespace: str) -> None:
        """Delete every key within a namespace."""
        pattern = self._key(namespace, "*")
        keys = await self._backend.scan_keys(pattern)
        if keys:
            await self._backend.delete(*keys)

    async def get_or_set(
        self,
        namespace: str,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: int | None = DEFAULT_TTL,
    ) -> T:
        """Return the cached value or compute, store, and return it."""
        cached = await self.get(namespace, key)
        if cached is not None:
            return cast("T", cached)
        value = await factory()
        await self.set(namespace, key, value, ttl)
        return value

    async def clear(self) -> None:
        await self._backend.clear()


def _build_backend() -> CacheBackend:
    try:
        return RedisCache(str(settings.redis_url))
    except Exception:
        logger.warning("cache.redis_unavailable_fallback_in_memory")
        return InMemoryCache()


_cache: CacheService | None = None


def get_cache() -> CacheService:
    """Return the process cache service singleton."""
    global _cache
    if _cache is None:
        _cache = CacheService(_build_backend())
    return _cache


def set_cache(service: CacheService) -> None:
    """Override the cache singleton (used in tests)."""
    global _cache
    _cache = service
