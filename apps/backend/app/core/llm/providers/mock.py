"""Deterministic mock provider.

Used in tests and as a safe default when no real provider is configured. It
echoes a predictable response derived from the request so the full framework
(services, retry, cache, cost, streaming, tools) can be exercised without a
network call or API key. It also honors ``response_schema`` by emitting a
minimal valid JSON object, and will emit a tool call when a tool named
``echo``/first tool is present and the last user message asks to "use tool".
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from app.core.llm.base import BaseLLMProvider
from app.core.llm.messages import (
    ChatRequest,
    ChatResponse,
    Role,
    StopReason,
    ToolCall,
    Usage,
)
from app.core.llm.streaming import StreamEvent, StreamEventType


def _last_user_text(request: ChatRequest) -> str:
    for message in reversed(request.messages):
        if message.role == Role.USER:
            return message.content
    return ""


def _schema_stub(schema: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal object satisfying a simple JSON schema's required fields."""
    props = schema.get("properties", {})
    required = schema.get("required", list(props))
    out: dict[str, Any] = {}
    for key in required:
        spec = props.get(key, {})
        typ = spec.get("type", "string")
        out[key] = {
            "string": "mock",
            "integer": 0,
            "number": 0,
            "boolean": False,
            "array": [],
            "object": {},
        }.get(typ, "mock")
    return out


class MockProvider(BaseLLMProvider):
    """A deterministic, network-free provider for tests and local defaults."""

    slug = "mock"

    def _build_response(self, request: ChatRequest) -> ChatResponse:
        user_text = _last_user_text(request)

        if request.response_schema is not None:
            content = json.dumps(_schema_stub(request.response_schema))
            return ChatResponse(
                content=content,
                model=request.model,
                usage=Usage(input_tokens=len(user_text.split()), output_tokens=5),
            )

        if request.tools and "use tool" in user_text.lower():
            tool = request.tools[0]
            call = ToolCall(id="mock_tool_1", name=tool["name"], arguments={})
            return ChatResponse(
                content="",
                model=request.model,
                stop_reason=StopReason.TOOL_USE,
                tool_calls=[call],
                usage=Usage(input_tokens=len(user_text.split()), output_tokens=2),
            )

        content = f"Echo: {user_text}" if user_text else "Hello from the mock provider."
        return ChatResponse(
            content=content,
            model=request.model,
            usage=Usage(
                input_tokens=max(len(user_text.split()), 1),
                output_tokens=max(len(content.split()), 1),
            ),
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        return self._build_response(request)

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        response = self._build_response(request)
        yield StreamEvent(type=StreamEventType.START)
        for token in response.content.split(" "):
            yield StreamEvent(type=StreamEventType.DELTA, text=token + " ")
        yield StreamEvent(type=StreamEventType.DONE, response=response)

    async def count_tokens(self, request: ChatRequest) -> int:
        return sum(len(m.content.split()) for m in request.messages)

    async def health_check(self) -> bool:
        return True
