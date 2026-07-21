"""API tests for the content endpoints and pagination envelope."""

from __future__ import annotations

import pytest
from app.core.events import EventBus, set_event_bus
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

_PW = "Str0ng!Passw0rd"


@pytest.fixture(autouse=True)
def _isolated_bus() -> None:
    set_event_bus(EventBus())


async def _auth(api: AsyncClient, email: str, username: str) -> dict[str, str]:
    await api.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": _PW},
    )
    tok = (
        await api.post("/api/v1/auth/login", json={"email": email, "password": _PW})
    ).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


async def _create_org(api: AsyncClient, headers: dict[str, str]) -> str:
    resp = await api.post("/api/v1/organizations", json={"name": "Acme"}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def test_workspace_project_video_flow(api: AsyncClient) -> None:
    headers = await _auth(api, "owner@example.com", "owner")
    org_id = await _create_org(api, headers)

    ws = await api.post(
        f"/api/v1/organizations/{org_id}/workspaces",
        json={"name": "Studio"},
        headers=headers,
    )
    assert ws.status_code == 201, ws.text
    ws_id = ws.json()["id"]
    assert ws.json()["version"] == 1

    proj = await api.post(
        f"/api/v1/organizations/{org_id}/workspaces/{ws_id}/projects",
        json={"name": "Launch"},
        headers=headers,
    )
    assert proj.status_code == 201
    proj_id = proj.json()["id"]

    video = await api.post(
        f"/api/v1/organizations/{org_id}/projects/{proj_id}/videos",
        json={"title": "Episode 1"},
        headers=headers,
    )
    assert video.status_code == 201
    assert video.json()["title"] == "Episode 1"


async def test_list_returns_pagination_envelope(api: AsyncClient) -> None:
    headers = await _auth(api, "owner2@example.com", "owner2")
    org_id = await _create_org(api, headers)
    for i in range(3):
        await api.post(
            f"/api/v1/organizations/{org_id}/workspaces",
            json={"name": f"WS {i}"},
            headers=headers,
        )
    resp = await api.get(
        f"/api/v1/organizations/{org_id}/workspaces?page=1&size=2", headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body and "meta" in body
    assert body["meta"]["pagination"]["total"] == 3
    assert body["meta"]["pagination"]["has_next"] is True
    assert len(body["data"]) == 2


async def test_content_requires_permission(api: AsyncClient) -> None:
    owner = await _auth(api, "o3@example.com", "owner3")
    org_id = await _create_org(api, owner)
    # A different user with no membership cannot create a workspace.
    outsider = await _auth(api, "out@example.com", "outsider")
    resp = await api.post(
        f"/api/v1/organizations/{org_id}/workspaces",
        json={"name": "Nope"},
        headers=outsider,
    )
    assert resp.status_code == 403


async def test_feature_flag_superuser_and_eval(
    api: AsyncClient, session: AsyncSession
) -> None:
    headers = await _auth(api, "su@example.com", "super")
    # Promote to superuser directly, then a fresh login reads the new flag.
    await session.execute(
        update(User).where(User.email == "su@example.com").values(is_superuser=True)
    )
    await session.commit()

    put = await api.put(
        "/api/v1/feature-flags",
        json={"key": "dashboard_v2", "enabled": True, "rollout_percentage": 100},
        headers=headers,
    )
    assert put.status_code == 200, put.text

    ev = await api.get("/api/v1/feature-flags/dashboard_v2", headers=headers)
    assert ev.status_code == 200
    assert ev.json()["enabled"] is True
