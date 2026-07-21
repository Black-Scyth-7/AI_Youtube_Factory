"""Tests for metadata and health endpoints."""

from __future__ import annotations

from app.__version__ import __version__
from fastapi.testclient import TestClient


def test_root_returns_service_metadata(client: TestClient) -> None:
    response = client.get("/api/v1/")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == __version__
    assert body["docs"] == "/docs"


def test_version_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == __version__
    assert body["environment"] == "test"


def test_health_endpoint_is_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_live_endpoint_is_ok(client: TestClient) -> None:
    response = client.get("/api/v1/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_schema_is_served(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["version"] == __version__


def test_request_id_header_is_present(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.headers.get("X-Request-ID")
    assert response.headers.get("X-Trace-ID")
