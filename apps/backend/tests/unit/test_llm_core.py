"""Unit tests for the LLM framework core (offline, mock provider)."""

from __future__ import annotations

import pytest
from app.core.llm.exceptions import (
    CircuitOpenError,
    LLMTimeoutError,
    PromptRenderError,
    StructuredOutputError,
)
from app.core.llm.manager import LLMManager
from app.core.llm.messages import ChatRequest, Message, ToolCall
from app.core.llm.models import estimate_cost, get_model_info
from app.core.llm.prompts import PromptEngine, PromptSpec, PromptVariable
from app.core.llm.providers import MockProvider
from app.core.llm.retry import CircuitBreaker, RetryPolicy, with_retry
from app.core.llm.schemas import extract_json, parse_structured
from app.core.llm.tokenizer import heuristic_token_count
from app.core.llm.tools import Tool, ToolRegistry
from pydantic import BaseModel

# -- Prompt engine -------------------------------------------------------
def test_prompt_render_with_variables() -> None:
    engine = PromptEngine()
    spec = PromptSpec(
        name="greet",
        template="Hello {{ name }}, you are {{ role }}.",
        variables=[PromptVariable("name"), PromptVariable("role", default="user")],
    )
    assert engine.render(spec, {"name": "Ada"}) == "Hello Ada, you are user."


def test_prompt_missing_required_raises() -> None:
    engine = PromptEngine()
    spec = PromptSpec(name="p", template="{{ x }}", variables=[PromptVariable("x")])
    with pytest.raises(PromptRenderError):
        engine.render(spec, {})


# -- Models / cost -------------------------------------------------------
def test_cost_estimate_opus() -> None:
    # 1M input + 1M output on opus-4-8 ($5 + $25).
    assert estimate_cost("claude-opus-4-8", 1_000_000, 1_000_000) == 30.0
    assert get_model_info("claude-opus-4-8").accepts_sampling_params is False


# -- Tokenizer -----------------------------------------------------------
def test_heuristic_token_count() -> None:
    req = ChatRequest(messages=[Message.user("a" * 40)], model="m")
    assert heuristic_token_count(req) == 10


# -- Structured output ---------------------------------------------------
def test_extract_json_from_fence() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_parse_structured_ok_and_error() -> None:
    class Out(BaseModel):
        a: int

    assert parse_structured('{"a": 5}', Out).a == 5
    with pytest.raises(StructuredOutputError):
        parse_structured("not json", Out)


# -- Retry / circuit breaker --------------------------------------------
async def test_retry_succeeds_after_failures() -> None:
    calls = {"n": 0}

    async def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise LLMTimeoutError()
        return "ok"

    result = await with_retry(flaky, policy=RetryPolicy(max_retries=3, base_delay=0))
    assert result == "ok" and calls["n"] == 3


async def test_circuit_breaker_opens() -> None:
    breaker = CircuitBreaker(failure_threshold=2)

    async def always_fail() -> None:
        raise LLMTimeoutError()

    for _ in range(2):
        with pytest.raises(LLMTimeoutError):
            await with_retry(
                always_fail,
                policy=RetryPolicy(max_retries=0, base_delay=0),
                breaker=breaker,
                key="p",
            )
    with pytest.raises(CircuitOpenError):
        await with_retry(
            always_fail, policy=RetryPolicy(max_retries=0), breaker=breaker, key="p"
        )


# -- Tools ---------------------------------------------------------------
async def test_tool_registry_execute() -> None:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="add",
            description="add",
            parameters={
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
            handler=lambda args: _add(args),
        )
    )
    result = await registry.execute(
        ToolCall(id="1", name="add", arguments={"a": 2, "b": 3})
    )
    assert result.content == "5" and result.is_error is False

    err = await registry.execute(ToolCall(id="2", name="unknown", arguments={}))
    assert err.is_error is True


async def _add(args: dict) -> str:
    return str(args["a"] + args["b"])


# -- Mock provider + manager --------------------------------------------
async def test_mock_provider_chat_and_stream() -> None:
    provider = MockProvider()
    resp = await provider.chat(ChatRequest(messages=[Message.user("hi")], model="m"))
    assert resp.content == "Echo: hi"

    chunks = [
        e
        async for e in provider.stream(
            ChatRequest(messages=[Message.user("hi there")], model="m")
        )
    ]
    assert chunks[-1].response is not None


async def test_manager_caches_response() -> None:
    from app.core.cache import CacheService, InMemoryCache, set_cache
    from app.core.llm.cache import LLMCache

    set_cache(CacheService(InMemoryCache()))
    manager = LLMManager(cache=LLMCache())
    request = ChatRequest(messages=[Message.user("cache me")], model="claude-opus-4-8")
    first = await manager.chat(request, provider_slug="mock")
    second = await manager.chat(request, provider_slug="mock")
    assert first.cache_hit is False
    assert second.cache_hit is True
