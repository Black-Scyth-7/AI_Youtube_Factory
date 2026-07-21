"""Workflow engine foundation.

Persists workflow graphs (nodes + edges) and executes them. The executor does a
topological walk of the graph, invoking a registered handler per node type and
threading a shared mutable context through the run. Node handlers are async and
pluggable so later phases (AI agents, render jobs) register real behavior. The
design is compatible with a future visual editor (nodes carry `position`).
"""

from __future__ import annotations

import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import WorkflowStarted, get_event_bus
from app.exceptions.base import NotFoundError, WorkflowError
from app.models.domain_enums import WorkflowExecutionStatus
from app.models.workflow import (
    Workflow,
    WorkflowEdge,
    WorkflowExecution,
    WorkflowNode,
)
from app.repositories.infra import WorkflowExecutionRepository, WorkflowRepository

NodeHandler = Callable[[WorkflowNode, dict[str, Any]], Awaitable[Any]]


async def _noop_handler(node: WorkflowNode, context: dict[str, Any]) -> Any:
    """Default handler — records that the node ran."""
    return {"node": node.key, "type": node.type}


class WorkflowService:
    """Builds workflow graphs and runs executions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.workflows = WorkflowRepository(session)
        self.executions = WorkflowExecutionRepository(session)
        self.events = get_event_bus()
        self._handlers: dict[str, NodeHandler] = {}

    def register_node(self, node_type: str, handler: NodeHandler) -> None:
        """Register a handler for a node type."""
        self._handlers[node_type] = handler

    async def create(
        self,
        *,
        workspace_id: uuid.UUID,
        name: str,
        actor_id: uuid.UUID,
        nodes: list[dict[str, Any]] | None = None,
        edges: list[dict[str, Any]] | None = None,
    ) -> Workflow:
        """Create a workflow with its nodes and edges."""
        workflow = await self.workflows.add(
            Workflow(
                workspace_id=workspace_id,
                name=name,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        for n in nodes or []:
            self.session.add(
                WorkflowNode(
                    workflow_id=workflow.id,
                    key=n["key"],
                    type=n.get("type", "noop"),
                    config=n.get("config", {}),
                    position=n.get("position", {}),
                    created_by=actor_id,
                    updated_by=actor_id,
                )
            )
        for e in edges or []:
            self.session.add(
                WorkflowEdge(
                    workflow_id=workflow.id,
                    source_key=e["source"],
                    target_key=e["target"],
                    condition=e.get("condition"),
                    created_by=actor_id,
                    updated_by=actor_id,
                )
            )
        await self.session.flush()
        return workflow

    async def _load_graph(
        self, workflow_id: uuid.UUID
    ) -> tuple[list[WorkflowNode], list[WorkflowEdge]]:
        nodes = (
            (
                await self.session.execute(
                    select(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
                )
            )
            .scalars()
            .all()
        )
        edges = (
            (
                await self.session.execute(
                    select(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id)
                )
            )
            .scalars()
            .all()
        )
        return list(nodes), list(edges)

    @staticmethod
    def _topological_order(
        nodes: list[WorkflowNode], edges: list[WorkflowEdge]
    ) -> list[WorkflowNode]:
        """Return nodes in dependency order; raise on a cycle."""
        by_key = {n.key: n for n in nodes}
        indegree: dict[str, int] = {n.key: 0 for n in nodes}
        adjacency: dict[str, list[str]] = defaultdict(list)
        for e in edges:
            if e.source_key in by_key and e.target_key in by_key:
                adjacency[e.source_key].append(e.target_key)
                indegree[e.target_key] += 1

        queue = deque(sorted(k for k, d in indegree.items() if d == 0))
        ordered: list[WorkflowNode] = []
        while queue:
            key = queue.popleft()
            ordered.append(by_key[key])
            for nxt in sorted(adjacency[key]):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        if len(ordered) != len(nodes):
            raise WorkflowError("Workflow graph contains a cycle.")
        return ordered

    async def execute(
        self, workflow_id: uuid.UUID, *, inputs: dict[str, Any] | None = None
    ) -> WorkflowExecution:
        """Execute a workflow end to end, recording status and logs."""
        workflow = await self.workflows.get(workflow_id)
        if workflow is None or workflow.deleted_at is not None:
            raise NotFoundError("Workflow not found.")

        execution = await self.executions.add(
            WorkflowExecution(
                workflow_id=workflow_id,
                status=WorkflowExecutionStatus.RUNNING.value,
                context=dict(inputs or {}),
                logs=[],
                started_at=datetime.now(UTC),
            )
        )
        await self.events.publish(
            WorkflowStarted(execution_id=execution.id, workflow_id=workflow_id)
        )

        nodes, edges = await self._load_graph(workflow_id)
        context = dict(inputs or {})
        logs: list[dict[str, Any]] = []
        try:
            for node in self._topological_order(nodes, edges):
                handler = self._handlers.get(node.type, _noop_handler)
                result = await handler(node, context)
                context[node.key] = result
                logs.append({"node": node.key, "status": "ok"})
            execution.status = WorkflowExecutionStatus.SUCCEEDED.value
        except Exception as exc:
            execution.status = WorkflowExecutionStatus.FAILED.value
            logs.append({"error": str(exc)})
        finally:
            execution.context = context
            execution.logs = logs
            execution.finished_at = datetime.now(UTC)
            await self.session.flush()
        return execution
