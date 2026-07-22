"""Token counting.

Delegates to the provider's authoritative token counter (cached), with a
heuristic fallback (~4 characters per token) when a provider count is
unavailable — never use tiktoken for Claude, its counts are wrong.
"""

from __future__ import annotations

from app.core.llm.base import BaseLLMProvider
from app.core.llm.cache import LLMCache
from app.core.llm.messages import ChatRequest

_CHARS_PER_TOKEN = 4


def heuristic_token_count(request: ChatRequest) -> int:
    """Rough token estimate used only when a provider count is unavailable."""
    chars = len(request.system or "")
    for message in request.messages:
        chars += len(message.content)
    return max(chars // _CHARS_PER_TOKEN, 1)


class TokenCounter:
    """Counts input tokens via the provider, with caching and a fallback."""

    def __init__(self, provider: BaseLLMProvider, cache: LLMCache | None = None) -> None:
        self._provider = provider
        self._cache = cache or LLMCache()

    async def count(self, request: ChatRequest) -> int:
        cached = await self._cache.get_token_count(request)
        if cached is not None:
            return cached
        try:
            count = await self._provider.count_tokens(request)
        except Exception:
            count = heuristic_token_count(request)
        await self._cache.set_token_count(request, count)
        return count
