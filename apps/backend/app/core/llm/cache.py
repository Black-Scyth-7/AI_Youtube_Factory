"""LLM response and token-count caching.

Builds deterministic cache keys from request content and stores results in the
shared Redis-backed cache (Phase 03). Caching is only applied to deterministic,
non-streaming, tool-free requests to avoid returning stale or partial results.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from app.config import settings
from app.core.cache import get_cache
from app.core.llm.messages import ChatRequest, ChatResponse, StopReason, Usage

_RESPONSE_NS = "llm:response"
_TOKENS_NS = "llm:tokens"


def _request_fingerprint(request: ChatRequest) -> str:
    payload = {
        "model": request.model,
        "system": request.system,
        "max_tokens": request.max_tokens,
        "messages": [
            {"role": m.role.value, "content": m.content} for m in request.messages
        ],
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def is_cacheable(request: ChatRequest) -> bool:
    """Return True if ``request`` is safe to cache."""
    return (
        settings.llm_cache_enabled
        and not request.tools
        and request.response_schema is None
    )


class LLMCache:
    """Read-through cache for chat responses and token counts."""

    def __init__(self) -> None:
        self._cache = get_cache()

    async def get_response(self, request: ChatRequest) -> ChatResponse | None:
        if not is_cacheable(request):
            return None
        data = await self._cache.get(_RESPONSE_NS, _request_fingerprint(request))
        if data is None:
            return None
        return ChatResponse(
            content=data["content"],
            model=data["model"],
            stop_reason=StopReason(data["stop_reason"]),
            usage=Usage(**data["usage"]),
        )

    async def set_response(self, request: ChatRequest, response: ChatResponse) -> None:
        if not is_cacheable(request):
            return
        payload = {
            "content": response.content,
            "model": response.model,
            "stop_reason": response.stop_reason.value,
            "usage": asdict(response.usage),
        }
        await self._cache.set(
            _RESPONSE_NS,
            _request_fingerprint(request),
            payload,
            ttl=settings.llm_cache_ttl_seconds,
        )

    async def get_token_count(self, request: ChatRequest) -> int | None:
        return await self._cache.get(_TOKENS_NS, _request_fingerprint(request))

    async def set_token_count(self, request: ChatRequest, count: int) -> None:
        await self._cache.set(
            _TOKENS_NS,
            _request_fingerprint(request),
            count,
            ttl=settings.llm_cache_ttl_seconds,
        )
