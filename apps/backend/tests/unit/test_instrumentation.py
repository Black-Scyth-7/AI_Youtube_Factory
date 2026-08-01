"""Tests that the application's own work is actually instrumented.

The registry is tested in ``test_observability``; these check the call sites —
that a stage failure is counted as a failure, that a gauge drains, and that
instrumentation never changes behaviour or swallows an error.
"""

from __future__ import annotations

from typing import Any

import pytest
from app.core.workflow import GraphEdge, GraphNode, WorkflowEngine, WorkflowGraph
from app.exceptions.base import WorkflowError
from app.observability import instruments
from app.observability.stages import record_artifact_size, track_stage
from app.observability.tracing import current_span


# -- Pipeline stages ----------------------------------------------------------
@pytest.mark.asyncio
async def test_a_successful_stage_is_counted_and_timed() -> None:
    before = instruments.pipeline_stages_total.value(
        stage="unit_test", outcome="succeeded"
    )
    calls = instruments.pipeline_stage_duration_seconds.count(stage="unit_test")

    @track_stage("unit_test")
    async def work(value: int) -> int:
        return value * 2

    assert await work(21) == 42
    assert (
        instruments.pipeline_stages_total.value(stage="unit_test", outcome="succeeded")
        == before + 1
    )
    assert (
        instruments.pipeline_stage_duration_seconds.count(stage="unit_test") == calls + 1
    )


@pytest.mark.asyncio
async def test_a_failing_stage_is_counted_as_failed_and_still_raises() -> None:
    """A stage that fails silently is worse than one that is not measured."""
    before = instruments.pipeline_stages_total.value(stage="unit_fail", outcome="failed")

    @track_stage("unit_fail")
    async def work() -> None:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await work()

    assert (
        instruments.pipeline_stages_total.value(stage="unit_fail", outcome="failed")
        == before + 1
    )


@pytest.mark.asyncio
async def test_a_stage_runs_inside_a_span() -> None:
    seen: list[str] = []

    @track_stage("unit_span")
    async def work() -> None:
        span = current_span()
        assert span is not None
        seen.append(span.name)

    await work()
    assert seen == ["pipeline.unit_span"]


@pytest.mark.asyncio
async def test_the_decorator_preserves_the_signature_and_docstring() -> None:
    """These methods are called with keyword arguments across the service."""

    @track_stage("unit_kwargs")
    async def work(a: int, *, b: int = 0) -> int:
        """Add two numbers."""
        return a + b

    assert await work(1, b=2) == 3
    assert work.__doc__ == "Add two numbers."
    assert work.__name__ == "work"


def test_an_artifact_without_a_size_is_not_recorded() -> None:
    """Not every stage produces bytes; a missing size is not a zero-byte file."""
    before = instruments.pipeline_artifact_bytes.count(stage="unit_artifact")
    record_artifact_size("unit_artifact", None)
    assert instruments.pipeline_artifact_bytes.count(stage="unit_artifact") == before

    record_artifact_size("unit_artifact", 2048)
    assert instruments.pipeline_artifact_bytes.count(stage="unit_artifact") == before + 1


# -- Workflow engine ----------------------------------------------------------
async def _noop(node: GraphNode, context: dict[str, Any]) -> Any:
    return node.key


@pytest.mark.asyncio
async def test_a_successful_run_is_counted_and_the_gauge_drains() -> None:
    runs = instruments.workflow_runs_total.value(outcome="succeeded")
    in_flight = instruments.workflow_runs_in_progress.value()

    engine = WorkflowEngine({"task": _noop})
    graph = WorkflowGraph(
        [GraphNode("a", "task"), GraphNode("b", "task")], [GraphEdge("a", "b")]
    )
    await engine.run(graph)

    assert instruments.workflow_runs_total.value(outcome="succeeded") == runs + 1
    assert instruments.workflow_runs_in_progress.value() == in_flight


@pytest.mark.asyncio
async def test_a_failed_run_is_counted_and_the_gauge_still_drains() -> None:
    """A gauge left incremented by a failure never returns to zero, and the
    saturation alert built on it fires forever."""
    failed = instruments.workflow_runs_total.value(outcome="failed")
    in_flight = instruments.workflow_runs_in_progress.value()

    async def explode(node: GraphNode, context: dict[str, Any]) -> Any:
        raise RuntimeError("boom")

    engine = WorkflowEngine({"task": explode})
    with pytest.raises(WorkflowError):
        await engine.run(WorkflowGraph([GraphNode("a", "task")], []))

    assert instruments.workflow_runs_total.value(outcome="failed") == failed + 1
    assert instruments.workflow_runs_in_progress.value() == in_flight


@pytest.mark.asyncio
async def test_node_outcomes_are_counted_separately() -> None:
    succeeded = instruments.workflow_nodes_total.value(
        node_type="task", outcome="succeeded"
    )
    skipped = instruments.workflow_nodes_total.value(node_type="task", outcome="skipped")

    engine = WorkflowEngine({"task": _noop})
    graph = WorkflowGraph(
        [GraphNode("a", "task"), GraphNode("b", "task")],
        [GraphEdge("a", "b", condition="1 == 2")],
    )
    await engine.run(graph)

    assert (
        instruments.workflow_nodes_total.value(node_type="task", outcome="succeeded")
        == succeeded + 1
    )
    assert (
        instruments.workflow_nodes_total.value(node_type="task", outcome="skipped")
        == skipped + 1
    )


# -- Storage ------------------------------------------------------------------
class _FakeStorage:
    """A storage client that does nothing, or fails on demand."""

    def __init__(self, *, fail: bool = False, healthy: bool = True) -> None:
        self.fail = fail
        self.healthy = healthy
        self.calls: list[str] = []

    async def put(self, key: str, data: bytes, content_type: str) -> str:
        self.calls.append("put")
        if self.fail:
            raise OSError("disk full")
        return key

    async def get(self, key: str) -> bytes:
        self.calls.append("get")
        if self.fail:
            raise OSError("missing")
        return b"payload"

    async def delete(self, key: str) -> None:
        self.calls.append("delete")

    async def presign_url(self, key: str, expires_in: int = 3600) -> str:
        self.calls.append("presign_url")
        return f"https://example.test/{key}"

    async def health_check(self) -> bool:
        self.calls.append("health_check")
        return self.healthy


def _metered(**kwargs: bool) -> Any:
    from app.core.storage.metered import MeteredStorageClient

    inner = _FakeStorage(**kwargs)
    return MeteredStorageClient(inner, "unit"), inner


@pytest.mark.asyncio
async def test_storage_calls_are_counted_and_delegated() -> None:
    client, inner = _metered()
    before = instruments.storage_operations_total.value(
        backend="unit", operation="put", outcome="success"
    )

    assert await client.put("k", b"data", "text/plain") == "k"
    assert await client.get("k") == b"payload"

    assert inner.calls == ["put", "get"]
    assert (
        instruments.storage_operations_total.value(
            backend="unit", operation="put", outcome="success"
        )
        == before + 1
    )


@pytest.mark.asyncio
async def test_a_storage_failure_is_counted_as_an_error_and_re_raised() -> None:
    client, _ = _metered(fail=True)
    before = instruments.storage_operations_total.value(
        backend="unit", operation="get", outcome="error"
    )

    with pytest.raises(OSError, match="missing"):
        await client.get("k")

    assert (
        instruments.storage_operations_total.value(
            backend="unit", operation="get", outcome="error"
        )
        == before + 1
    )


@pytest.mark.asyncio
async def test_a_reachable_but_unhealthy_backend_is_neither_success_nor_error() -> None:
    """The distinction is the whole point of a health check."""
    client, _ = _metered(healthy=False)
    before = instruments.storage_operations_total.value(
        backend="unit", operation="health_check", outcome="unhealthy"
    )

    assert await client.health_check() is False
    assert (
        instruments.storage_operations_total.value(
            backend="unit", operation="health_check", outcome="unhealthy"
        )
        == before + 1
    )


def test_get_storage_returns_an_instrumented_client() -> None:
    """Wiring check: instrumentation that is never installed measures nothing."""
    from app.core.storage import get_storage
    from app.core.storage.metered import MeteredStorageClient

    assert isinstance(get_storage(), MeteredStorageClient)


def test_create_storage_client_still_returns_the_concrete_provider() -> None:
    """The wrapper belongs in get_storage(), so the factory stays inspectable."""
    from app.core.storage import (
        LocalStorageProvider,
        StorageProvider,
        create_storage_client,
    )

    assert isinstance(create_storage_client(StorageProvider.LOCAL), LocalStorageProvider)
