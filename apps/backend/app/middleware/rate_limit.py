"""Fixed-window rate limiting middleware.

Applies a per-client-IP request budget using a Redis counter. If Redis is
unavailable or rate limiting is disabled, the middleware passes every request
through, so it never takes the API down on infrastructure failure.
"""

from __future__ import annotations

from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.logging import get_logger

logger = get_logger(__name__)

_WINDOW_SECONDS = 60
_MAX_REQUESTS = 300


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Limit requests per client IP within a fixed time window."""

    def __init__(self, app: Any) -> None:
        super().__init__(app)
        self._client: Any = None
        self._enabled = settings.rate_limit_enabled

    async def _get_client(self) -> Any:
        if not self._enabled:
            return None
        if self._client is None:
            try:
                import redis.asyncio as redis

                self._client = redis.from_url(str(settings.redis_url))
            except Exception:
                self._enabled = False
                return None
        return self._client

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client = await self._get_client()
        if client is not None:
            ip = request.client.host if request.client else "anonymous"
            key = f"ratelimit:{ip}"
            try:
                count = await client.incr(key)
                if count == 1:
                    await client.expire(key, _WINDOW_SECONDS)
                if count > _MAX_REQUESTS:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": {
                                "code": "rate_limited",
                                "message": "Too many requests.",
                            }
                        },
                    )
            except Exception:
                self._enabled = False
        return await call_next(request)
