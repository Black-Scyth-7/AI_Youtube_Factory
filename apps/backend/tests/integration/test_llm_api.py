"""Integration tests for the LLM API (mock provider, offline)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.core.cache import CacheService, InMemoryCache, set_cache
from app.core.llm.manager import LLMManager, set_llm_manager
from app.core.llm.registry import reset_providers
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

_PW = "Str0ng!Passw0rd"


@pytest.fixture(autouse=True)
def _reset_llm() -> None:
    """Isolate LLM singletons and cache per test."""
    set_cache(CacheService(InMemoryCache()))
    reset_providers()
    set_llm_manager(LLMManager())


async def _auth(api: AsyncClient, email: str, username: str) -> dict[str, str]:
    await api.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": _PW},
    )
    tok = (
        await api.post("/api/v1/auth/login", json={"email": email, "password": _PW})
    ).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def _org(api: AsyncClient, headers: dict[str, str]) -> str:
    resp = await api.post("/api/v1/organizations", json={"name": "Acme"}, headers=headers)
    return resp.json()["id"]


async def test_chat_returns_response_and_records_usage(api: AsyncClient) -> None:
    headers = await _auth(api, "ai@example.com", "aiuser")
    org_id = await _org(api, headers)

    resp = await api.post(
        "/api/v1/llm/chat",
        json={
            "messages": [{"role": "user", "content": "hello world"}],
            "organization_id": org_id,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["content"] == "Echo: hello world"
    assert body["provider"] == "mock"
    assert body["usage"]["total_tokens"] > 0

    today = datetime.now(UTC).date().isoformat()
    usage = await api.get(
        f"/api/v1/llm/usage?organization_id={org_id}&start={today}&end={today}",
        headers=headers,
    )
    assert usage.status_code == 200
    assert usage.json()["request_count"] >= 1

    costs = await api.get(
        f"/api/v1/llm/costs?organization_id={org_id}&start={today}&end={today}",
        headers=headers,
    )
    assert costs.status_code == 200


async def test_models_and_health(api: AsyncClient) -> None:
    headers = await _auth(api, "m@example.com", "modeluser")
    models = await api.get("/api/v1/llm/models", headers=headers)
    assert models.status_code == 200
    assert any(m["id"] == "claude-opus-4-8" for m in models.json())

    health = await api.get("/api/v1/llm/health", headers=headers)
    assert health.status_code == 200
    mock_health = next(h for h in health.json() if h["provider"] == "mock")
    assert mock_health["healthy"] is True


async def test_tools_endpoint(api: AsyncClient) -> None:
    headers = await _auth(api, "t@example.com", "tooluser")
    resp = await api.get("/api/v1/llm/tools", headers=headers)
    assert resp.status_code == 200
    assert any(t["name"] == "echo" for t in resp.json())


async def test_prompt_lifecycle(api: AsyncClient) -> None:
    headers = await _auth(api, "p@example.com", "promptuser")
    org_id = await _org(api, headers)

    created = await api.post(
        "/api/v1/llm/prompts",
        json={
            "organization_id": org_id,
            "name": "greeting",
            "template": "Hello {{ name }}!",
            "variables": [{"name": "name", "required": True}],
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    tid = created.json()["id"]
    assert created.json()["latest_version"] == 1

    rendered = await api.post(
        f"/api/v1/llm/prompts/{tid}/render",
        json={"context": {"name": "Ada"}},
        headers=headers,
    )
    assert rendered.status_code == 200
    assert rendered.json()["rendered"] == "Hello Ada!"

    # New version bumps head.
    v2 = await api.post(
        f"/api/v1/llm/prompts/{tid}/versions",
        json={"template": "Hi {{ name }}!", "variables": [{"name": "name"}]},
        headers=headers,
    )
    assert v2.json()["latest_version"] == 2


async def test_conversation_persists_turns(api: AsyncClient) -> None:
    headers = await _auth(api, "c@example.com", "convouser")
    org_id = await _org(api, headers)

    convo = await api.post(
        "/api/v1/llm/conversations",
        json={"organization_id": org_id, "title": "Chat"},
        headers=headers,
    )
    assert convo.status_code == 201
    cid = convo.json()["id"]

    await api.post(
        "/api/v1/llm/chat",
        json={
            "messages": [{"role": "user", "content": "remember this"}],
            "organization_id": org_id,
            "conversation_id": cid,
        },
        headers=headers,
    )
    msgs = await api.get(f"/api/v1/llm/conversations/{cid}/messages", headers=headers)
    assert msgs.status_code == 200
    roles = [m["role"] for m in msgs.json()]
    assert roles == ["user", "assistant"]


async def test_chat_requires_membership(api: AsyncClient) -> None:
    owner = await _auth(api, "own@example.com", "owneruser")
    org_id = await _org(api, owner)
    outsider = await _auth(api, "outs@example.com", "outsideruser")
    resp = await api.post(
        "/api/v1/llm/chat",
        json={
            "messages": [{"role": "user", "content": "hi"}],
            "organization_id": org_id,
        },
        headers=outsider,
    )
    assert resp.status_code == 403
