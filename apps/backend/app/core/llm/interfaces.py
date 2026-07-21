"""LLM provider abstraction — interfaces.

Defines the provider-agnostic contract that every LLM backend (Claude, OpenAI,
Gemini, DeepSeek, local models) must satisfy. No provider is implemented in
Phase 01 — the concrete Claude provider lands in Phase 04. Application code must
depend only on these abstractions, never on a concrete SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class LLMProvider(StrEnum):
    """Known provider identifiers (implementations added incrementally)."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    LOCAL = "local"


@dataclass(slots=True, frozen=True)
class Message:
    """A single conversation message."""

    role: str
    content: str


@dataclass(slots=True, frozen=True)
class CompletionRequest:
    """A provider-agnostic completion request."""

    messages: list[Message]
    model: str
    max_tokens: int = 1024
    system: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class TokenUsage:
    """Token accounting for a single completion."""

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(slots=True, frozen=True)
class CompletionResponse:
    """A provider-agnostic completion result."""

    content: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)


@runtime_checkable
class LLMClient(Protocol):
    """The contract all concrete LLM providers implement."""

    provider: LLMProvider

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Return a completion for ``request``."""
        ...

    async def health_check(self) -> bool:
        """Return ``True`` if the provider is reachable and configured."""
        ...
