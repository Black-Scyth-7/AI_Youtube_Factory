"""Fixed-window rate limiting middleware.

Applies a request budget using a Redis counter. If Redis is unavailable the
middleware passes requests through rather than taking the API down on an
infrastructure failure — but it *retries*, rather than disabling itself forever
after one blip (see ``_cooldown``).

Public-API requests are limited per API key rather than per IP. Many keys sit
behind one NAT address, and one noisy integration should not throttle every
other customer sharing it.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Final

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.logging import get_logger
from app.security.tokens import API_KEY_PREFIX

logger = get_logger(__name__)

_WINDOW_SECONDS: Final = 60
_MAX_REQUESTS: Final = 300
#: Public API keys get their own, tighter budget.
_API_KEY_MAX_REQUESTS: Final = 120
#: How long to stop calling Redis after a failure before trying again. Without
#: this the middleware used to set a flag that was never cleared, so a single
#: transient error disabled rate limiting for the lifetime of the process.
_COOLDOWN_SECONDS: Final = 30


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limit requests per client within a fixed time window."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._client: Any = None
        self._cooldown_until = 0.0

    def _degrade(self, reason: str) -> None:
        """Stop calling Redis briefly, then try again."""
        first = self._cooldown_until <= time.monotonic()
        self._cooldown_until = time.monotonic() + _COOLDOWN_SECONDS
        self._client = None
        if first:
            logger.warning(
                "ratelimit.degraded",
                extra={"reason": reason, "cooldown_seconds": _COOLDOWN_SECONDS},
            )

    async def _get_client(self) -> Any:
        if not settings.rate_limit_enabled:
            return None
        if time.monotonic() < self._cooldown_until:
            return None
        if self._client is None:
            try:
                import redis.asyncio as redis

                self._client = redis.from_url(str(settings.redis_url))
            except Exception as exc:
                self._degrade(str(exc))
                return None
        return self._client

    @staticmethod
    def _presented_key(request: Request) -> str | None:
        """The raw API key on the request, if one was sent.

        Session JWTs arrive on the same ``Authorization: Bearer`` header, so a
        bearer value only counts as an API key when it carries the API-key
        prefix. Without that check every logged-in user would be metered
        against the tighter public-API budget.
        """
        explicit = request.headers.get("X-API-Key")
        if explicit and explicit.startswith(API_KEY_PREFIX):
            return explicit.strip()

        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        token = token.strip()
        if scheme.lower() == "bearer" and token.startswith(API_KEY_PREFIX):
            return token
        return None

    def _bucket(self, request: Request) -> tuple[str, int]:
        """The counter key for this request, and its budget.

        A public-API request is bucketed by its key, so one integration cannot
        exhaust the budget of everything else behind the same NAT address.

        The bucket is derived from a hash of the *presented* credential, not
        from the authenticated principal: middleware runs before dependencies,
        so no principal exists yet. Hashing also means a forged key gets its own
        bucket — keying on the plaintext prefix would let anyone who learned it
        burn through someone else's budget.
        """
        presented = self._presented_key(request)
        if presented:
            digest = hashlib.sha256(presented.encode()).hexdigest()[:32]
            return f"ratelimit:key:{digest}", _API_KEY_MAX_REQUESTS
        ip = request.client.host if request.client else "anonymous"
        return f"ratelimit:ip:{ip}", _MAX_REQUESTS

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client = await self._get_client()
        if client is None:
            return await call_next(request)

        key, budget = self._bucket(request)
        try:
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, _WINDOW_SECONDS)
        except Exception as exc:
            self._degrade(str(exc))
            return await call_next(request)

        if count > budget:
            retry_after = str(_WINDOW_SECONDS)
            return JSONResponse(
                status_code=429,
                content={
                    "error": {"code": "rate_limited", "message": "Too many requests."}
                },
                # Without Retry-After a client has to guess, and the usual guess
                # is "immediately", which is what turns a limit into a loop.
                headers={
                    "Retry-After": retry_after,
                    "X-RateLimit-Limit": str(budget),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(budget)
        response.headers["X-RateLimit-Remaining"] = str(max(budget - count, 0))
        return response
