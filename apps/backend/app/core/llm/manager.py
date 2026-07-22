"""LLM manager — the orchestration core.

Wraps a resolved provider with the cross-cutting concerns every request needs:
response caching, retries + circuit breaking, rate limiting (RPM + concurrency),
and observability. The service layer calls :meth:`chat` / :meth:`stream`; nothing
else touches providers directly. This keeps "no direct Anthropic calls outside
the provider layer" true by construction.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.config import settings
from app.core.llm.base import BaseLLMProvider
from app.core.llm.cache import LLMCache
from app.core.llm.exceptions import LLMRateLimitError
from app.core.llm.messages import ChatRequest, ChatResponse, Usage
from app.core.llm.metrics import RequestTimer, record_request
from app.core.llm.registry import get_provider
from app.core.llm.retry import CircuitBreaker, RetryPolicy, with_retry
from app.core.llm.streaming import StreamEvent
from app.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class ChatOutcome:
    """The result of a managed chat call, with observability metadata."""

    response: ChatResponse
    provider: str
    latency_ms: float
    cost_usd: float
    cache_hit: bool = False


class RateLimiter:
    """RPM (Redis-backed, graceful) + in-process concurrency limiter."""

    def __init__(self) -> None:
        self._semaphore = asyncio.Semaphore(settings.llm_rate_limit_concurrent)

    async def check_rpm(self, key: str) -> None:
        if not settings.llm_cache_enabled:
            return
        try:
            import redis.asyncio as redis

            client = redis.from_url(str(settings.redis_url))
            bucket = f"llm:rpm:{key}"
            count = await client.incr(bucket)
            if count == 1:
                await client.expire(bucket, 60)
            await client.aclose()
            if count > settings.llm_rate_limit_rpm:
                raise LLMRateLimitError(
                    details={"key": key, "limit": settings.llm_rate_limit_rpm}
                )
        except LLMRateLimitError:
            raise
        except Exception:
            return

    def slot(self) -> asyncio.Semaphore:
        return self._semaphore


class LLMManager:
    """Coordinates provider access with caching, retries, and limits."""

    def __init__(
        self,
        *,
        cache: LLMCache | None = None,
        breaker: CircuitBreaker | None = None,
        limiter: RateLimiter | None = None,
    ) -> None:
        self._cache = cache or LLMCache()
        self._breaker = breaker or CircuitBreaker()
        self._limiter = limiter or RateLimiter()

    def _resolve(self, provider_slug: str | None) -> BaseLLMProvider:
        return get_provider(provider_slug or settings.llm_default_provider)

    async def chat(
        self,
        request: ChatRequest,
        *,
        provider_slug: str | None = None,
        rate_limit_key: str = "global",
    ) -> ChatOutcome:
        """Execute a managed, non-streaming chat request."""
        provider = self._resolve(provider_slug)
        timer = RequestTimer()

        cached = await self._cache.get_response(request)
        if cached is not None:
            cost = record_request(
                provider=provider.slug,
                model=request.model,
                usage=cached.usage,
                latency_ms=timer.elapsed_ms,
                cache_hit=True,
            )
            return ChatOutcome(
                response=cached,
                provider=provider.slug,
                latency_ms=timer.elapsed_ms,
                cost_usd=cost,
                cache_hit=True,
            )

        await self._limiter.check_rpm(rate_limit_key)
        policy = RetryPolicy(max_retries=settings.llm_max_retries)

        async with self._limiter.slot():
            try:
                response = await with_retry(
                    lambda: provider.chat(request),
                    policy=policy,
                    breaker=self._breaker,
                    key=provider.slug,
                )
            except Exception as exc:
                record_request(
                    provider=provider.slug,
                    model=request.model,
                    usage=Usage(),
                    latency_ms=timer.elapsed_ms,
                    error=str(exc),
                )
                raise

        await self._cache.set_response(request, response)
        cost = record_request(
            provider=provider.slug,
            model=request.model,
            usage=response.usage,
            latency_ms=timer.elapsed_ms,
            tool_calls=len(response.tool_calls),
        )
        return ChatOutcome(
            response=response,
            provider=provider.slug,
            latency_ms=timer.elapsed_ms,
            cost_usd=cost,
        )

    async def stream(
        self,
        request: ChatRequest,
        *,
        provider_slug: str | None = None,
        rate_limit_key: str = "global",
    ) -> AsyncIterator[StreamEvent]:
        """Execute a managed streaming chat request, yielding StreamEvents."""
        provider = self._resolve(provider_slug)
        await self._limiter.check_rpm(rate_limit_key)
        timer = RequestTimer()
        final_response = None
        async with self._limiter.slot():
            async for event in provider.stream(request):
                if event.response is not None:
                    final_response = event.response
                yield event
        if final_response is not None:
            record_request(
                provider=provider.slug,
                model=request.model,
                usage=final_response.usage,
                latency_ms=timer.elapsed_ms,
                streamed=True,
            )

    async def count_tokens(
        self, request: ChatRequest, *, provider_slug: str | None = None
    ) -> int:
        from app.core.llm.tokenizer import TokenCounter

        return await TokenCounter(self._resolve(provider_slug), self._cache).count(
            request
        )


_manager: LLMManager | None = None


def get_llm_manager() -> LLMManager:
    """Return the process LLM-manager singleton."""
    global _manager
    if _manager is None:
        _manager = LLMManager()
    return _manager


def set_llm_manager(manager: LLMManager) -> None:
    """Override the LLM-manager singleton (used in tests)."""
    global _manager
    _manager = manager
