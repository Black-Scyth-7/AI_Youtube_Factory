"""Integration tests for the agent API (mock provider, offline)."""

from __future__ import annotations

import pytest
from app.agents.manager.manager import AgentManager, set_agent_manager
from app.agents.monitoring.monitor import AgentMonitor, set_agent_monitor
from app.core.cache import CacheService, InMemoryCache, set_cache
from app.core.llm.manager import LLMManager, set_llm_manager
from app.core.llm.registry import reset_providers
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

_PW = "Str0ng!Passw0rd"


@pytest.fixture(autouse=True)
def _reset() -> None:
    """Isolate singletons per test."""
    set_cache(CacheService(InMemoryCache()))
    reset_providers()
    set_llm_manager(LLMManager())
    set_agent_manager(AgentManager())
    set_agent_monitor(AgentMonitor())


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


async def test_list_agents_catalog(api: AsyncClient) -> None:
    headers = await _auth(api, "a@example.com", "agentuser")
    resp = await api.get("/api/v1/agents", headers=headers)
    assert resp.status_code == 200
    slugs = {a["slug"] for a in resp.json()}
    assert {"echo", "assistant", "research"} <= slugs


async def test_start_agent_persists_run(api: AsyncClient) -> None:
    headers = await _auth(api, "run@example.com", "runuser")
    org_id = await _org(api, headers)

    resp = await api.post(
        "/api/v1/agents/start",
        json={
            "slug": "assistant",
            "objective": "Summarize unit testing",
            "organization_id": org_id,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["goal_status"] == "completed"
    run_id = body["run_id"]

    tasks = await api.get(f"/api/v1/tasks?run_id={run_id}", headers=headers)
    assert tasks.status_code == 200
    assert len(tasks.json()) >= 1

    evaluation = await api.get(f"/api/v1/evaluations/{run_id}", headers=headers)
    assert evaluation.status_code == 200
    assert evaluation.json()["overall"] >= 0

    reflection = await api.get(f"/api/v1/reflections/{run_id}", headers=headers)
    assert reflection.status_code == 200

    goals = await api.get(f"/api/v1/goals?organization_id={org_id}", headers=headers)
    assert goals.status_code == 200
    assert len(goals.json()) >= 1

    metrics = await api.get(f"/api/v1/metrics?organization_id={org_id}", headers=headers)
    assert metrics.status_code == 200
    assert metrics.json()["runs"] >= 1


async def test_tools_catalog(api: AsyncClient) -> None:
    headers = await _auth(api, "tool@example.com", "tooluser")
    resp = await api.get("/api/v1/tools", headers=headers)
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()}
    assert "calculator" in names


async def test_plan_preview_and_reason(api: AsyncClient) -> None:
    headers = await _auth(api, "plan@example.com", "planuser")
    plan = await api.post(
        "/api/v1/plans/preview",
        json={"objective": "Write a blog post about Python"},
        headers=headers,
    )
    assert plan.status_code == 200
    assert len(plan.json()["tasks"]) >= 1

    reason = await api.post(
        "/api/v1/reason",
        json={"objective": "Write a post", "task": "Draft the intro"},
        headers=headers,
    )
    assert reason.status_code == 200
    assert reason.json()["thought"]


async def test_knowledge_crud(api: AsyncClient) -> None:
    headers = await _auth(api, "kn@example.com", "knuser")
    org_id = await _org(api, headers)

    created = await api.post(
        "/api/v1/knowledge",
        json={
            "organization_id": org_id,
            "title": "Brand voice",
            "content": "Friendly and concise.",
            "kind": "preference",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    doc_id = created.json()["id"]

    listing = await api.get(
        f"/api/v1/knowledge?organization_id={org_id}", headers=headers
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    deleted = await api.delete(f"/api/v1/knowledge/{doc_id}", headers=headers)
    assert deleted.status_code == 200


async def test_agent_control_endpoints(api: AsyncClient) -> None:
    headers = await _auth(api, "ctl@example.com", "ctluser")
    import uuid

    fake = uuid.uuid4()
    resp = await api.post(
        "/api/v1/agents/stop", json={"run_id": str(fake)}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["acted"] is False
