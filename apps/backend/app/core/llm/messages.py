"""Provider-neutral message and request/response types.

These are the canonical types every provider translates to and from. Application
and service code depends only on these — never on a concrete SDK's types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    """Conversation roles (superset supported across providers)."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    DEVELOPER = "developer"


class StopReason(StrEnum):
    """Why generation stopped."""

    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    STOP_SEQUENCE = "stop_sequence"
    TOOL_USE = "tool_use"
    REFUSAL = "refusal"
    ERROR = "error"


@dataclass(slots=True)
class ToolCall:
    """A model request to invoke a tool."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolResult:
    """The result of executing a tool, fed back to the model."""

    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass(slots=True)
class Message:
    """A single conversation message.

    ``content`` is plain text; ``tool_calls`` (assistant) and ``tool_results``
    (tool/user turn) carry structured tool interactions.
    """

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    name: str | None = None

    @classmethod
    def user(cls, content: str) -> Message:
        return cls(role=Role.USER, content=content)

    @classmethod
    def assistant(cls, content: str) -> Message:
        return cls(role=Role.ASSISTANT, content=content)

    @classmethod
    def system(cls, content: str) -> Message:
        return cls(role=Role.SYSTEM, content=content)


@dataclass(slots=True, frozen=True)
class Usage:
    """Token accounting for a single request/response."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
        )


@dataclass(slots=True)
class ChatRequest:
    """A provider-neutral chat request."""

    messages: list[Message]
    model: str
    max_tokens: int = 4096
    system: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    stop_sequences: list[str] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    thinking: bool = True
    response_schema: dict[str, Any] | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class ChatResponse:
    """A provider-neutral chat response."""

    content: str
    model: str
    stop_reason: StopReason = StopReason.END_TURN
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_message(self) -> Message:
        """Convert this response into an assistant message for history."""
        return Message(
            role=Role.ASSISTANT, content=self.content, tool_calls=self.tool_calls
        )
