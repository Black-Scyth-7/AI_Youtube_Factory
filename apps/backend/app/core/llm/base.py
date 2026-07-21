"""LLM provider abstraction — base class.

Provides a common base that concrete providers extend. Keeps shared behaviour
(provider identity, request validation hooks) in one place. Concrete providers
are implemented in Phase 04.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.llm.interfaces import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
)


class BaseLLMClient(ABC):
    """Abstract base for all LLM providers.

    Subclasses must set :attr:`provider` and implement :meth:`complete` and
    :meth:`health_check`.
    """

    provider: LLMProvider

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Return a completion for ``request``."""
        raise NotImplementedError

    @abstractmethod
    async def health_check(self) -> bool:
        """Return ``True`` if the provider is reachable and configured."""
        raise NotImplementedError
