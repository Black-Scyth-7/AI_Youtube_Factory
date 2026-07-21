"""Brute-force login protection.

Tracks failed login attempts per identifier in Redis and locks out after a
threshold. Degrades to a permissive no-op when Redis is unavailable (e.g. unit
tests), so it never blocks the auth flow on infrastructure errors.
"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.exceptions.base import UnauthorizedError
from app.logging import get_logger

logger = get_logger(__name__)


class LoginGuard:
    """Redis-backed failed-attempt counter with lockout."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or str(settings.redis_url)
        self._client: Any = None

    async def _get_client(self) -> Any:
        if not settings.rate_limit_enabled:
            return None
        if self._client is None:
            try:
                import redis.asyncio as redis

                self._client = redis.from_url(self._redis_url)
            except Exception:
                return None
        return self._client

    def _key(self, identifier: str) -> str:
        return f"login:attempts:{identifier.lower()}"

    async def check(self, identifier: str) -> None:
        """Raise if ``identifier`` is currently locked out."""
        client = await self._get_client()
        if client is None:
            return
        try:
            attempts = await client.get(self._key(identifier))
        except Exception:
            return
        if attempts is not None and int(attempts) >= settings.login_max_attempts:
            raise UnauthorizedError(
                "Too many failed login attempts. Try again later.",
            )

    async def record_failure(self, identifier: str) -> None:
        """Increment the failed-attempt counter, setting a lockout window."""
        client = await self._get_client()
        if client is None:
            return
        try:
            key = self._key(identifier)
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, settings.login_lockout_seconds)
        except Exception:
            return

    async def reset(self, identifier: str) -> None:
        """Clear the counter after a successful login."""
        client = await self._get_client()
        if client is None:
            return
        try:
            await client.delete(self._key(identifier))
        except Exception:
            return
