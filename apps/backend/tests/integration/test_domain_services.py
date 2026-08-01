"""Tests for content services, workflow execution, and feature flags."""

from __future__ import annotations

import uuid

import pytest
from app.core.cache import CacheService, InMemoryCache, set_cache
from app.core.events import (
    Event,
    EventBus,
    ProjectCreated,
    VideoCreated,
    WorkspaceCreated,
    set_event_bus,
)
from app.core.workflow import GraphEdge, GraphNode, WorkflowGraph
from app.exceptions.base import WorkflowError
from app.models.domain_enums import FeatureFlagScope, WorkflowExecutionStatus
from app.services.content import ProjectService, VideoService, WorkspaceService
from app.services.feature_flags import FeatureFlagService
from app.services.workflow import WorkflowService
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def capture_events() -> list[Event]:
    """Install a fresh event bus that records published events."""
    bus = EventBus()
    captured: list[Event] = []

    async def _record(event: Event) -> None:
        captured.append(event)

    for etype in (WorkspaceCreated, ProjectCreated, VideoCreated):
        bus.subscribe(etype, _record)
    set_event_bus(bus)
    return captured


async def test_content_hierarchy_and_events(
    session: AsyncSession, capture_events: list[Event]
) -> None:
    org, actor = uuid.uuid4(), uuid.uuid4()
    ws = await WorkspaceService(session).create(
        organization_id=org, name="Studio", actor_id=actor
    )
    project = await ProjectService(session).create(
        workspace_id=ws.id, name="Launch", actor_id=actor
    )
    video = await VideoService(session).create(
        project_id=project.id, title="Episode 1", actor_id=actor
    )
    version = await VideoService(session).add_version(
        video_id=video.id, script="Hello world", actor_id=actor
    )

    assert ws.created_by == actor and ws.version == 1
    assert version.version_number == 1
    refreshed = await VideoService(session).repo.get(video.id)
    assert refreshed is not None and refreshed.current_version_id == version.id

    names = {type(e).__name__ for e in capture_events}
    assert {"WorkspaceCreated", "ProjectCreated", "VideoCreated"} <= names


async def test_duplicate_slug_gets_suffix(session: AsyncSession) -> None:
    org, actor = uuid.uuid4(), uuid.uuid4()
    a = await WorkspaceService(session).create(
        organization_id=org, name="Dup", actor_id=actor, slug="dup"
    )
    b = await WorkspaceService(session).create(
        organization_id=org, name="Dup", actor_id=actor, slug="dup"
    )
    assert a.slug == "dup"
    assert b.slug != "dup" and b.slug.startswith("dup-")


async def test_workflow_execution_topological(session: AsyncSession) -> None:
    set_event_bus(EventBus())
    actor = uuid.uuid4()
    service = WorkflowService(session)
    order: list[str] = []

    async def handler(node, context):
        order.append(node.key)
        return node.key

    service.register_node("step", handler)
    wf = await service.create(
        workspace_id=uuid.uuid4(),
        name="pipeline",
        actor_id=actor,
        nodes=[
            {"key": "a", "type": "step"},
            {"key": "b", "type": "step"},
            {"key": "c", "type": "step"},
        ],
        edges=[{"source": "a", "target": "b"}, {"source": "b", "target": "c"}],
    )
    execution = await service.execute(wf.id, inputs={"seed": 1})
    assert execution.status == WorkflowExecutionStatus.SUCCEEDED.value
    assert order == ["a", "b", "c"]
    assert execution.context["a"] == "a"


async def test_workflow_cycle_is_detected(session: AsyncSession) -> None:
    set_event_bus(EventBus())
    service = WorkflowService(session)
    wf = await service.create(
        workspace_id=uuid.uuid4(),
        name="cycle",
        actor_id=uuid.uuid4(),
        nodes=[{"key": "a", "type": "noop"}, {"key": "b", "type": "noop"}],
        edges=[{"source": "a", "target": "b"}, {"source": "b", "target": "a"}],
    )
    execution = await service.execute(wf.id)
    # The executor captures the WorkflowError and marks the run failed.
    assert execution.status == WorkflowExecutionStatus.FAILED.value
    assert any("cycle" in str(entry).lower() for entry in execution.logs)


async def test_cycle_detection_raises_directly() -> None:
    """Ordering moved from WorkflowService onto the engine's graph in Phase 07.

    The behaviour this covered — a cyclic graph is rejected rather than looping
    — still matters, so it is asserted against its new home.
    """
    graph = WorkflowGraph(
        [GraphNode("a", "noop"), GraphNode("b", "noop")],
        [GraphEdge("a", "b"), GraphEdge("b", "a")],
    )
    with pytest.raises(WorkflowError, match="cycle"):
        graph.levels()


async def test_feature_flag_scopes(session: AsyncSession) -> None:
    set_cache(CacheService(InMemoryCache()))
    service = FeatureFlagService(session)
    user = uuid.uuid4()

    # Global on.
    await service.set_flag(key="new_ui", enabled=True)
    assert await service.is_enabled("new_ui") is True

    # Disabled flag is always off.
    await service.set_flag(key="beta", enabled=False)
    assert await service.is_enabled("beta", user_id=user) is False

    # User-scoped explicit target.
    await service.set_flag(
        key="early",
        enabled=True,
        scope=FeatureFlagScope.USER,
        targets=[str(user)],
    )
    assert await service.is_enabled("early", user_id=user) is True
    assert await service.is_enabled("early", user_id=uuid.uuid4()) is False

    # 100% rollout is always on for global.
    await service.set_flag(key="ga", enabled=True, rollout_percentage=100)
    assert await service.is_enabled("ga") is True
