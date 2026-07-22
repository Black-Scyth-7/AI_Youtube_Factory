"""Streaming abstraction.

Providers emit a uniform sequence of :class:`StreamEvent` objects regardless of
their native wire format, so the service/API layers and the frontend consume one
event shape. Supports token deltas, tool-call signals, and a terminal event
carrying the final response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.llm.messages import ChatResponse


class StreamEventType(StrEnum):
    """Kinds of streaming events."""

    START = "start"
    DELTA = "delta"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    ERROR = "error"
    DONE = "done"


@dataclass(slots=True)
class StreamEvent:
    """A single streaming event."""

    type: StreamEventType
    text: str = ""
    response: ChatResponse | None = None
    error: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def to_sse(self) -> str:
        """Serialize as a Server-Sent Events ``data:`` line payload."""
        import json

        payload = {"type": self.type.value, "text": self.text}
        if self.error:
            payload["error"] = self.error
        return json.dumps(payload)
