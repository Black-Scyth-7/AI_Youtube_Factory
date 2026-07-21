"""Cache backends.

Defines the :class:`CacheBackend` protocol plus two implementations: an
in-process :class:`InMemoryCache` (used in tests and as a graceful fallback) and
a :class:`RedisCache` for distributed caching in production.
"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable


@runtime_checkable
class CacheBackend(Protocol):
    """Low-level string key/value cache with TTL."""

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str, ttl: int | None = None) -> None: ...

    async def delete(self, *keys: str) -> None: ...

    async def scan_keys(self, pattern: str) -> list[str]: ...

    async def clear(self) -> None: ...


class InMemoryCache(CacheBackend):
    """A process-local cache with per-key expiry. Not shared across workers."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}

    async def get(self, key: str) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires = entry
        if expires is not None and expires < time.monotonic():
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        expires = time.monotonic() + ttl if ttl else None
        self._store[key] = (value, expires)

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self._store.pop(key, None)

    async def scan_keys(self, pattern: str) -> list[str]:
        prefix = pattern.rstrip("*")
        return [k for k in self._store if k.startswith(prefix)]

    async def clear(self) -> None:
        self._store.clear()


class RedisCache(CacheBackend):
    """A Redis-backed distributed cache."""

    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as redis

        self._client = redis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        value = await self._client.get(key)
        return value if value is None else str(value)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        await self._client.set(key, value, ex=ttl)

    async def delete(self, *keys: str) -> None:
        if keys:
            await self._client.delete(*keys)

    async def scan_keys(self, pattern: str) -> list[str]:
        found: list[str] = []
        async for key in self._client.scan_iter(match=pattern):
            found.append(key)
        return found

    async def clear(self) -> None:
        await self._client.flushdb()
