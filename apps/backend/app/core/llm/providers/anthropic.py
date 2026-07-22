"""Anthropic (Claude) provider.

The only place in the codebase that talks to the Anthropic SDK. Translates the
neutral :class:`ChatRequest`/:class:`ChatResponse` to and from the Messages API.

Follows current API rules: adaptive thinking (``{"type": "adaptive"}``) rather
than a token budget, and sampling parameters (``temperature``/``top_p``/
``top_k``) are sent **only** for models that accept them — Opus 4.7/4.8,
Sonnet 5, and Fable 5 reject them.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.config import settings
from app.core.llm.base import BaseLLMProvider
from app.core.llm.exceptions import LLMError, ProviderNotAvailableError
from app.core.llm.messages import (
    ChatRequest,
    ChatResponse,
    Role,
    StopReason,
    ToolCall,
    Usage,
)
from app.core.llm.models import get_model_info
from app.core.llm.streaming import StreamEvent, StreamEventType
from app.logging import get_logger

logger = get_logger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Claude provider backed by the official Anthropic Python SDK."""

    slug = "anthropic"

    def __init__(self, api_key: str | None = None, client: Any = None) -> None:
        self._api_key = api_key or settings.anthropic_api_key
        self._client = client  # injectable for tests

    @property
    def client(self) -> Any:
        """Lazily construct the async Anthropic client."""
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover - dependency guard
                raise ProviderNotAvailableError(
                    "The 'anthropic' package is not installed."
                ) from exc
            if not self._api_key:
                raise ProviderNotAvailableError("ANTHROPIC_API_KEY is not configured.")
            self._client = anthropic.AsyncAnthropic(
                api_key=self._api_key, timeout=settings.llm_timeout_seconds
            )
        return self._client

    # -- Translation ------------------------------------------------------
    def _split_system(self, request: ChatRequest) -> tuple[str | None, list[Any]]:
        """Separate system text from the conversation messages (Anthropic API)."""
        system_parts: list[str] = []
        if request.system:
            system_parts.append(request.system)

        messages: list[dict[str, Any]] = []
        for message in request.messages:
            if message.role in (Role.SYSTEM, Role.DEVELOPER):
                if message.content:
                    system_parts.append(message.content)
                continue
            messages.append(self._render_message(message))

        system = "\n\n".join(system_parts) if system_parts else None
        return system, messages

    @staticmethod
    def _render_message(message: Any) -> dict[str, Any]:
        if message.role == Role.ASSISTANT:
            blocks: list[dict[str, Any]] = []
            if message.content:
                blocks.append({"type": "text", "text": message.content})
            for call in message.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call.id,
                        "name": call.name,
                        "input": call.arguments,
                    }
                )
            return {"role": "assistant", "content": blocks or message.content}

        # user / tool -> user turn (tool results are user-role blocks)
        blocks = []
        for result in message.tool_results:
            blocks.append(
                {
                    "type": "tool_result",
                    "tool_use_id": result.tool_call_id,
                    "content": result.content,
                    "is_error": result.is_error,
                }
            )
        if message.content:
            blocks.append({"type": "text", "text": message.content})
        return {"role": "user", "content": blocks or message.content}

    def _build_params(self, request: ChatRequest) -> dict[str, Any]:
        info = get_model_info(request.model)
        system, messages = self._split_system(request)
        params: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "messages": messages,
        }
        if system:
            params["system"] = system
        if request.stop_sequences:
            params["stop_sequences"] = request.stop_sequences
        if request.tools:
            params["tools"] = request.tools
        if request.thinking and info.adaptive_thinking_only:
            params["thinking"] = {"type": "adaptive"}
        # Sampling params only for models that accept them.
        if info.accepts_sampling_params:
            if request.temperature is not None:
                params["temperature"] = request.temperature
            if request.top_p is not None:
                params["top_p"] = request.top_p
            if request.top_k is not None:
                params["top_k"] = request.top_k
        return params

    @staticmethod
    def _parse_response(message: Any, model: str) -> ChatResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in message.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=dict(block.input))
                )
        usage = getattr(message, "usage", None)
        return ChatResponse(
            content="".join(text_parts),
            model=model,
            stop_reason=_map_stop_reason(getattr(message, "stop_reason", None)),
            tool_calls=tool_calls,
            usage=Usage(
                input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
                output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
                cache_read_tokens=(
                    getattr(usage, "cache_read_input_tokens", 0) or 0 if usage else 0
                ),
            ),
        )

    # -- Provider interface ----------------------------------------------
    async def chat(self, request: ChatRequest) -> ChatResponse:
        try:
            message = await self.client.messages.create(**self._build_params(request))
        except Exception as exc:
            raise LLMError(f"Anthropic request failed: {exc}") from exc
        return self._parse_response(message, request.model)

    async def stream(self, request: ChatRequest) -> AsyncIterator[StreamEvent]:
        params = self._build_params(request)
        try:
            async with self.client.messages.stream(**params) as stream:
                yield StreamEvent(type=StreamEventType.START)
                async for text in stream.text_stream:
                    yield StreamEvent(type=StreamEventType.DELTA, text=text)
                final = await stream.get_final_message()
        except Exception as exc:
            yield StreamEvent(type=StreamEventType.ERROR, error=str(exc))
            return
        yield StreamEvent(
            type=StreamEventType.DONE, response=self._parse_response(final, request.model)
        )

    async def count_tokens(self, request: ChatRequest) -> int:
        system, messages = self._split_system(request)
        params: dict[str, Any] = {"model": request.model, "messages": messages}
        if system:
            params["system"] = system
        result = await self.client.messages.count_tokens(**params)
        return int(result.input_tokens)

    async def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            await self.client.messages.count_tokens(
                model=settings.llm_default_model,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception as exc:
            logger.warning("llm.anthropic.health_failed", extra={"error": str(exc)})
            return False


def _map_stop_reason(value: str | None) -> StopReason:
    mapping = {
        "end_turn": StopReason.END_TURN,
        "max_tokens": StopReason.MAX_TOKENS,
        "stop_sequence": StopReason.STOP_SEQUENCE,
        "tool_use": StopReason.TOOL_USE,
        "refusal": StopReason.REFUSAL,
    }
    return mapping.get(value or "", StopReason.END_TURN)
