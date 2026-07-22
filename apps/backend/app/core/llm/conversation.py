"""In-memory conversation object.

A lightweight, provider-neutral conversation that accumulates messages and builds
:class:`ChatRequest` objects. Persistence lives in the conversation service; this
is the runtime representation used while a turn is being processed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.llm.messages import ChatRequest, Message, Role


@dataclass(slots=True)
class Conversation:
    """A sequence of messages with a system prompt and metadata."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    system: str | None = None
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add(self, message: Message) -> None:
        self.messages.append(message)

    def add_user(self, content: str) -> None:
        self.add(Message.user(content))

    def add_assistant(self, content: str) -> None:
        self.add(Message.assistant(content))

    def to_request(self, *, model: str, max_tokens: int, **kwargs: Any) -> ChatRequest:
        """Build a :class:`ChatRequest` from the conversation state."""
        return ChatRequest(
            messages=[m for m in self.messages if m.role != Role.SYSTEM],
            model=model,
            max_tokens=max_tokens,
            system=self.system,
            **kwargs,
        )
