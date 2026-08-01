"""Workflow engine foundation.

Persists workflow graphs (nodes + edges) and executes them. The executor does a
topological walk of the graph, invoking a registered handler per node type and
threading a shared mutable context through the run. Node handlers are async and
pluggable so later phases (AI agents, render jobs) register real behavior. The
design is compatible with a future visual editor (nodes carry `position`).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import WorkflowStarted, get_event_bus
from app.core.workflow import (
    GraphEdge,
    GraphNode,
    NodeOutcome,
    WorkflowEngine,
    WorkflowGraph,
)
from app.exceptions.base import NotFoundError, WorkflowError
from app.models.domain_enums import WorkflowExecutionStatus
from app.models.workflow import (
    Workflow,
    WorkflowEdge,
    WorkflowExecution,
    WorkflowNode,
    WorkflowNodeExecution,
)
from app.repositories.infra import WorkflowExecutionRepository, WorkflowRepository

NodeHandler = Callable[[WorkflowNode, dict[str, Any]], Awaitable[Any]]


async def _noop_handler(node: WorkflowNode, context: dict[str, Any]) -> Any:
    """Default handler — records that the node ran."""
    return {"node": node.key, "type": node.type}


def _adapt_handler(
    handler: NodeHandler,
) -> Callable[[GraphNode, dict[str, Any]], Awaitable[Any]]:
    """Let a handler written against the ORM node accept a GraphNode.

    Registered handlers predate the engine and expect ``.key``/``.type``/
    ``.config``, all of which GraphNode also provides, so the value passes
    straight through.
    """

    async def wrapper(node: GraphNode, context: dict[str, Any]) -> Any:
        return await handler(node, context)  # type: ignore[arg-type]

    return wrapper


def _jsonable(value: Any) -> Any:
    """Coerce a value into something the JSON columns can store.

    Handler output is arbitrary; anything unserialisable is recorded as its
    string form rather than failing the run at flush time.
    """
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return {"repr": repr(value)}
    if isinstance(value, dict):
        return value
    return value


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

    def _build_graph(
        self, nodes: list[WorkflowNode], edges: list[WorkflowEdge]
    ) -> WorkflowGraph:
        """Map ORM rows onto the database-free graph the engine executes."""
        return WorkflowGraph(
            [GraphNode(key=n.key, type=n.type, config=n.config) for n in nodes],
            [
                GraphEdge(source=e.source_key, target=e.target_key, condition=e.condition)
                for e in edges
            ],
        )

    def _engine(self) -> WorkflowEngine:
        """An engine carrying the handlers registered on this service.

        Handlers take an ORM ``WorkflowNode`` for backwards compatibility, so
        each is wrapped to accept the engine's plain ``GraphNode``.
        """
        engine = WorkflowEngine()
        for node_type, handler in self._handlers.items():
            engine.register(node_type, _adapt_handler(handler))
        return engine

    async def _record_outcomes(
        self, execution: WorkflowExecution, outcomes: list[NodeOutcome]
    ) -> None:
        for outcome in outcomes:
            self.session.add(
                WorkflowNodeExecution(
                    execution_id=execution.id,
                    node_key=outcome.key,
                    node_type=outcome.type,
                    status=outcome.status,
                    iteration=outcome.iteration,
                    output=_jsonable(outcome.output),
                    error=outcome.error,
                    skip_reason=outcome.skip_reason,
                )
            )
        await self.session.flush()

    async def execute(
        self, workflow_id: uuid.UUID, *, inputs: dict[str, Any] | None = None
    ) -> WorkflowExecution:
        """Execute a workflow end to end, recording status, logs and per-node rows."""
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
        outcomes: list[NodeOutcome] = []
        try:
            graph = self._build_graph(nodes, edges)
            context, outcomes = await self._engine().run(graph, context)
            logs = [
                {"node": o.key, "status": o.status, "iteration": o.iteration}
                for o in outcomes
            ]
            execution.status = WorkflowExecutionStatus.SUCCEEDED.value
        except WorkflowError as exc:
            execution.status = WorkflowExecutionStatus.FAILED.value
            # The engine attaches the outcomes gathered before it stopped.
            raw = (exc.details or {}).get("outcomes", [])
            outcomes = [NodeOutcome(**item) for item in raw]
            logs = [{"error": str(exc)}]
        except Exception as exc:
            execution.status = WorkflowExecutionStatus.FAILED.value
            logs = [{"error": str(exc)}]
        finally:
            execution.context = _jsonable(context)
            execution.logs = logs
            execution.finished_at = datetime.now(UTC)
            await self.session.flush()
            await self._record_outcomes(execution, outcomes)
        return execution
