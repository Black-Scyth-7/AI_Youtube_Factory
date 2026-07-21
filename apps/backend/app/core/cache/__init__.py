"""Redis-backed cache layer with an in-memory fallback."""

from app.core.cache.backend import CacheBackend, InMemoryCache, RedisCache
from app.core.cache.service import (
    DEFAULT_TTL,
    CacheService,
    get_cache,
    set_cache,
)

__all__ = [
    "DEFAULT_TTL",
    "CacheBackend",
    "CacheService",
    "InMemoryCache",
    "RedisCache",
    "get_cache",
    "set_cache",
]
