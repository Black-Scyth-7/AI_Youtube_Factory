"""LLM bridge for the agent runtime.

The agent engine reasons, plans, and reflects through the Phase 04 LLM
framework — never by touching a provider or the Anthropic SDK directly. This
module defines a minimal :class:`AgentLLM` protocol plus a default
:class:`ManagerLLM` implementation backed by the shared :class:`LLMManager`
(which works offline against the mock provider, so the whole engine is testable
without an API key).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.config import settings
from app.core.llm.manager import LLMManager, get_llm_manager
from app.core.llm.messages import ChatRequest, Message


@dataclass(slots=True)
class LLMReply:
    """A completion result with the accounting the agent needs."""

    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@runtime_checkable
class AgentLLM(Protocol):
    """The narrow LLM surface the agent engine depends on."""

    async def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int | None = None
    ) -> LLMReply: ...


class ManagerLLM:
    """Default :class:`AgentLLM` backed by the shared LLM manager."""

    def __init__(
        self,
        *,
        manager: LLMManager | None = None,
        model: str | None = None,
        rate_limit_key: str = "agent",
    ) -> None:
        self._manager = manager or get_llm_manager()
        self._model = model or settings.llm_default_model
        self._rate_limit_key = rate_limit_key

    async def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int | None = None
    ) -> LLMReply:
        """Run a single-turn completion and return the text + usage."""
        request = ChatRequest(
            messages=[Message.user(prompt)],
            model=self._model,
            system=system or settings.llm_system_prompt,
            max_tokens=max_tokens or settings.llm_max_tokens,
            thinking=settings.llm_thinking == "adaptive",
        )
        outcome = await self._manager.chat(request, rate_limit_key=self._rate_limit_key)
        usage = outcome.response.usage
        return LLMReply(
            text=outcome.response.content,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_usd=outcome.cost_usd,
            model=outcome.response.model,
        )
