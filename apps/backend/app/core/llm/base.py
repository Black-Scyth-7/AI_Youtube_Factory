"""LLM provider abstraction — base classes.

Defines :class:`BaseLLMProvider`, the full provider contract every backend
implements (chat, stream, complete, embed, token counting, cost estimation,
capability flags, health). Application/service code depends only on this
abstraction — never on a concrete SDK. The legacy :class:`BaseLLMClient` is kept
for backward compatibility with Phase 01.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.core.llm.interfaces import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
)
from app.core.llm.messages import ChatRequest, ChatResponse
from app.core.llm.models import estimate_cost, get_model_info
from app.core.llm.streaming import StreamEvent


class BaseLLMClient(ABC):
    """Legacy Phase 01 provider base (retained for backward compatibility)."""

    provider: LLMProvider

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Return a completion for ``request``."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the provider is reachable and configured."""
        raise NotImplementedError


class BaseLLMProvider(ABC):
    """The contract every LLM provider implements.

    Concrete providers translate the neutral :class:`ChatRequest` /
    :class:`ChatResponse` to and from their SDK. Capability and cost helpers have
    catalog-backed defaults; providers override only what differs.
    """

    #: Stable provider slug (e.g. ``"anthropic"``, ``"mock"``).
    slug: str

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Return a single, complete chat response."""
        raise NotImplementedError

    @abstractmethod
    def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        """Stream a chat response as a sequence of :class:`StreamEvent`."""
        raise NotImplementedError

    async def complete(self, prompt: str, *, model: str, max_tokens: int = 1024) -> str:
        """Convenience: single-prompt completion returning text."""
        from app.core.llm.messages import Message

        response = await self.chat(
            ChatRequest(
                messages=[Message.user(prompt)], model=model, max_tokens=max_tokens
            )
        )
        return response.content

    async def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        """Return embeddings for ``texts`` (providers that support embeddings)."""
        raise NotImplementedError(f"{self.slug} does not support embeddings.")

    @abstractmethod
    async def count_tokens(self, request: ChatRequest) -> int:
        """Return the input token count for ``request``."""
        raise NotImplementedError

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Return the estimated USD cost (catalog-backed)."""
        return estimate_cost(model, input_tokens, output_tokens)

    def supports_tools(self, model: str) -> bool:
        return get_model_info(model).supports_tools

    def supports_images(self, model: str) -> bool:
        return get_model_info(model).supports_images

    def supports_streaming(self, model: str) -> bool:
        return get_model_info(model).supports_streaming

    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the provider is reachable and configured."""
        raise NotImplementedError
