"""Tests for the scrape endpoint and the HTTP instrumentation around it."""

from __future__ import annotations

import io
import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from app.config import settings
from app.middleware.metrics import UNMATCHED_ROUTE
from app.observability import metrics
from app.observability.tracing import SpanContext
from fastapi.testclient import TestClient


def _series(body: str, name: str) -> dict[str, float]:
    """Parse the samples of one metric out of an exposition payload."""
    found: dict[str, float] = {}
    for line in body.splitlines():
        if line.startswith("#") or not line.startswith(name):
            continue
        labels, _, value = line.rpartition(" ")
        if labels.split("{")[0] == name:
            found[labels] = float(value)
    return found


# -- The endpoint -------------------------------------------------------------


def test_metrics_endpoint_serves_the_prometheus_format(client: TestClient) -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"] == metrics.CONTENT_TYPE
    assert "# HELP http_requests_total" in response.text
    assert "# TYPE http_requests_total counter" in response.text


def test_the_scrape_endpoint_is_distinct_from_the_agent_report(
    client: TestClient,
) -> None:
    """``/api/v1/metrics`` is the agents' JSON report and needs auth; the
    scrape endpoint is a different, unversioned endpoint serving exposition
    text. Their route labels must not collide either — see
    ``test_colliding_route_names_stay_separate``."""
    agent_report = client.get(f"{settings.api_v1_prefix}/metrics")
    assert agent_report.status_code == 401

    scrape = client.get("/metrics")
    assert scrape.status_code == 200
    assert scrape.headers["content-type"] == metrics.CONTENT_TYPE


def test_metrics_are_absent_from_the_openapi_schema(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/metrics" not in schema["paths"]


def test_disabled_metrics_return_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disabled must look like never-mounted, not like forbidden."""
    monkeypatch.setattr(settings, "metrics_enabled", False)
    assert client.get("/metrics").status_code == 404


def test_a_configured_token_is_required(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "metrics_token", "s3cret-scrape-token")

    unauthenticated = client.get("/metrics")
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["www-authenticate"] == "Bearer"
    # The payload must not leak while unauthorized.
    assert "http_requests_total" not in unauthenticated.text

    assert (
        client.get("/metrics", headers={"Authorization": "Basic abc"}).status_code == 401
    )
    assert (
        client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )

    authorized = client.get(
        "/metrics", headers={"Authorization": "Bearer s3cret-scrape-token"}
    )
    assert authorized.status_code == 200
    assert "http_requests_total" in authorized.text


# -- Cardinality --------------------------------------------------------------


def test_route_label_is_the_template_not_the_path(client: TestClient) -> None:
    """The whole point of the route label: one series per route, not per URL.

    Labelling by the raw path would give a series per id, which is unbounded
    and client-controlled.
    """
    slugs = ("alpha-agent", "beta-agent", "gamma-agent")
    for slug in slugs:
        # 401 without a token, which is fine: the request is still counted, and
        # counting it is exactly where an unbounded label would leak.
        client.get(f"{settings.api_v1_prefix}/agents/{slug}")

    series = _series(client.get("/metrics").text, "http_requests_total")
    # One series for the route, whatever the slug was. Other tests exercise
    # other /agents routes, so this asserts the shape rather than the count.
    matching = [key for key in series if "/agents/{slug}" in key]
    assert matching, f"expected a templated /agents/{{slug}} series, got {sorted(series)}"
    assert not any(slug in "".join(series) for slug in slugs)


def test_unmatched_paths_share_one_series(client: TestClient) -> None:
    """A 404 probe sweep must not create a series per probed path."""
    for path in ("/wp-admin", "/.env", "/phpmyadmin"):
        client.get(path)

    series = _series(client.get("/metrics").text, "http_requests_total")
    unmatched = [key for key in series if UNMATCHED_ROUTE in key]
    assert unmatched, "404s should be counted, not dropped"
    assert not any(probe in "".join(series) for probe in ("wp-admin", "phpmyadmin"))


def test_colliding_route_names_stay_separate(client: TestClient) -> None:
    """Two routes both ending in /metrics must not share one series.

    Route labels come from the full template; the per-router template would
    render both as "/metrics" and silently merge them.
    """
    client.get("/metrics")
    client.get(f"{settings.api_v1_prefix}/metrics")

    series = _series(client.get("/metrics").text, "http_requests_total")
    routes = {key.split('route="')[1].split('"')[0] for key in series}
    assert "/metrics" in routes
    assert f"{settings.api_v1_prefix}/metrics" in routes


# -- What gets recorded -------------------------------------------------------


def test_requests_are_counted_by_status_class(client: TestClient) -> None:
    before = _series(client.get("/metrics").text, "http_requests_total")
    route = f"{settings.api_v1_prefix}/health"
    key = f'http_requests_total{{method="GET",route="{route}",status="2xx"}}'
    baseline = before.get(key, 0.0)

    client.get(f"{settings.api_v1_prefix}/health")
    client.get(f"{settings.api_v1_prefix}/health")

    after = _series(client.get("/metrics").text, "http_requests_total")
    assert after[key] == baseline + 2


def test_latency_is_observed_for_every_request(client: TestClient) -> None:
    client.get(f"{settings.api_v1_prefix}/health")
    body = client.get("/metrics").text
    counts = _series(body, "http_request_duration_seconds_count")
    sums = _series(body, "http_request_duration_seconds_sum")
    key = f'{{method="GET",route="{settings.api_v1_prefix}/health"}}'
    assert counts[f"http_request_duration_seconds_count{key}"] >= 1
    assert sums[f"http_request_duration_seconds_sum{key}"] > 0


def test_in_flight_gauge_returns_to_zero(client: TestClient) -> None:
    """A gauge that never drains makes a saturation alert fire forever."""
    client.post(f"{settings.api_v1_prefix}/auth/login", json={})
    series = _series(client.get("/metrics").text, "http_requests_in_progress")
    assert series['http_requests_in_progress{method="POST"}'] == 0
    # The scrape itself is the one GET still in flight while rendering.
    assert series['http_requests_in_progress{method="GET"}'] == 1


def test_build_info_is_exposed(client: TestClient) -> None:
    body = client.get("/metrics").text
    assert re.search(r'app_info\{version="[^"]+",environment="[^"]+"\} 1', body)


# -- Correlation --------------------------------------------------------------


def test_response_carries_correlation_headers(client: TestClient) -> None:
    response = client.get(f"{settings.api_v1_prefix}/health")
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])
    assert SpanContext.parse(response.headers["traceparent"]) is not None
    assert response.headers["x-trace-id"] in response.headers["traceparent"]


def test_an_inbound_traceparent_is_continued(client: TestClient) -> None:
    """A request crossing services must stay on one trace id."""
    inbound = SpanContext("a" * 32, "b" * 16)
    response = client.get(
        f"{settings.api_v1_prefix}/health",
        headers={"traceparent": inbound.to_traceparent()},
    )
    outbound = SpanContext.parse(response.headers["traceparent"])
    assert outbound is not None
    assert outbound.trace_id == inbound.trace_id
    # A new span of that trace, not an echo of the caller's.
    assert outbound.span_id != inbound.span_id


def test_a_malformed_traceparent_does_not_fail_the_request(client: TestClient) -> None:
    response = client.get(
        f"{settings.api_v1_prefix}/health", headers={"traceparent": "not-a-header"}
    )
    assert response.status_code == 200
    assert SpanContext.parse(response.headers["traceparent"]) is not None


def test_a_hostile_request_id_is_not_reflected(client: TestClient) -> None:
    """The id is echoed to the client and written into logs, so it is bounded."""
    response = client.get(
        f"{settings.api_v1_prefix}/health",
        headers={"X-Request-ID": "<script>alert(1)</script>"},
    )
    assert "<script>" not in response.headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


def test_a_sane_request_id_is_preserved(client: TestClient) -> None:
    response = client.get(
        f"{settings.api_v1_prefix}/health", headers={"X-Request-ID": "abc-123_XYZ.7"}
    )
    assert response.headers["x-request-id"] == "abc-123_XYZ.7"


@contextmanager
def _capture_json_logs(logger_name: str) -> Iterator[list[dict[str, object]]]:
    """Capture log records formatted *as they are emitted*.

    ``caplog`` stores records and formats them afterwards, but the JSON
    formatter reads the request id and trace id from context variables at
    format time — by which point the request has ended and both are None. Only
    formatting inline, the way a real handler does, tests what gets shipped.
    """
    from app.logging.config import JsonLogFormatter

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLogFormatter())
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    previous = logger.level
    logger.setLevel(logging.INFO)
    entries: list[dict[str, object]] = []
    try:
        yield entries
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous)
        entries.extend(
            json.loads(line) for line in stream.getvalue().splitlines() if line
        )


def test_access_log_carries_the_correlation_ids(client: TestClient) -> None:
    """Regression: the access log used to be emitted after a `finally` that had
    already cleared the context, so every successful request logged a null
    request id — the one field that makes an access log searchable."""
    with _capture_json_logs("app.middleware.request_context") as entries:
        response = client.get(f"{settings.api_v1_prefix}/health")

    completed = [e for e in entries if e.get("message") == "request.completed"]
    assert completed, "the access log should be emitted"
    assert completed[-1]["request_id"] == response.headers["x-request-id"]
    assert completed[-1]["trace_id"] == response.headers["x-trace-id"]
    assert completed[-1]["status_code"] == 200


def test_logs_from_inside_a_handler_share_the_request_trace(client: TestClient) -> None:
    """Correlation is only useful if application logs join the access log."""
    with _capture_json_logs("app") as entries:
        response = client.get(f"{settings.api_v1_prefix}/health")

    traced = [e for e in entries if e.get("trace_id")]
    assert traced
    assert {e["trace_id"] for e in traced} == {response.headers["x-trace-id"]}
