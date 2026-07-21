"""API-level authentication flow tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

_PASSWORD = "Str0ng!Passw0rd"


async def _register(api: AsyncClient, email: str = "alice@example.com") -> dict:
    resp = await api.post(
        "/api/v1/auth/register",
        json={"email": email, "username": "alice", "password": _PASSWORD},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _login(api: AsyncClient, email: str = "alice@example.com") -> dict:
    resp = await api.post(
        "/api/v1/auth/login", json={"email": email, "password": _PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_register_returns_user(api: AsyncClient) -> None:
    body = await _register(api)
    assert body["email"] == "alice@example.com"
    assert body["is_verified"] is False
    assert "password_hash" not in body


async def test_register_rejects_weak_password(api: AsyncClient) -> None:
    resp = await api.post(
        "/api/v1/auth/register",
        json={"email": "b@example.com", "username": "bob", "password": "weak"},
    )
    assert resp.status_code == 422


async def test_register_duplicate_email_conflicts(api: AsyncClient) -> None:
    await _register(api)
    resp = await api.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "username": "alice2", "password": _PASSWORD},
    )
    assert resp.status_code == 409


async def test_login_and_me(api: AsyncClient) -> None:
    await _register(api)
    tokens = await _login(api)
    assert tokens["token_type"] == "bearer"
    me = await api.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


async def test_login_wrong_password_is_unauthorized(api: AsyncClient) -> None:
    await _register(api)
    resp = await api.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "Wr0ng!Passw0rd"},
    )
    assert resp.status_code == 401


async def test_login_unknown_email_is_generic_401(api: AsyncClient) -> None:
    resp = await api.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": _PASSWORD},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["message"] == "Invalid email or password."


async def test_refresh_rotation(api: AsyncClient) -> None:
    await _register(api)
    tokens = await _login(api)
    resp = await api.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200
    new_tokens = resp.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # Old refresh token must be rejected (rotation / replay protection).
    replay = await api.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert replay.status_code == 401


async def test_logout_revokes_session(api: AsyncClient) -> None:
    await _register(api)
    tokens = await _login(api)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    out = await api.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )
    assert out.status_code == 200
    # Access token is now bound to a revoked session.
    me = await api.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 401


async def test_me_requires_auth(api: AsyncClient) -> None:
    resp = await api.get("/api/v1/users/me")
    assert resp.status_code == 401
