"""Workflow graph execution.

The Phase 03 walk ran every node in topological order and ignored edge
conditions entirely — a condition could be authored but never had any effect.
This engine evaluates them, so a false condition prunes the branch behind it,
and runs independent nodes concurrently instead of one at a time.

Pure graph logic lives here, free of the database, so it can be reasoned about
and tested on plain dataclasses. The service layer maps ORM rows onto these.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from typing import Any, Final

from app.core.workflow.expressions import evaluate, evaluate_condition
from app.exceptions.base import WorkflowError
from app.models.domain_enums import NodeKind, NodeRunStatus

#: Ceiling on loop passes, so a mis-authored loop cannot run forever.
MAX_LOOP_ITERATIONS: Final = 1000


@dataclass(slots=True, frozen=True)
class GraphNode:
    key: str
    type: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class GraphEdge:
    source: str
    target: str
    condition: str | None = None


@dataclass(slots=True)
class NodeOutcome:
    key: str
    type: str
    status: str
    iteration: int = 0
    output: Any = None
    error: str | None = None
    skip_reason: str | None = None


NodeHandler = Callable[[GraphNode, dict[str, Any]], Awaitable[Any]]


async def _default_handler(node: GraphNode, context: dict[str, Any]) -> Any:
    return {"node": node.key, "type": node.type}


class WorkflowGraph:
    """A validated graph, ready to execute."""

    def __init__(self, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
        self.nodes = {n.key: n for n in nodes}
        if len(self.nodes) != len(nodes):
            raise WorkflowError("Duplicate node keys in workflow graph.")

        # Edges pointing at nodes that do not exist are a definition error, not
        # something to silently ignore at run time.
        for edge in edges:
            if edge.source not in self.nodes or edge.target not in self.nodes:
                raise WorkflowError(
                    "Edge references an unknown node.",
                    details={"source": edge.source, "target": edge.target},
                )
        self.edges = edges
        self.incoming: dict[str, list[GraphEdge]] = defaultdict(list)
        self.outgoing: dict[str, list[GraphEdge]] = defaultdict(list)
        for edge in edges:
            self.incoming[edge.target].append(edge)
            self.outgoing[edge.source].append(edge)

    def levels(self) -> list[list[GraphNode]]:
        """Group nodes into dependency levels.

        Everything in one level is independent of everything else in it, so a
        level can run concurrently. Raises on a cycle.
        """
        indegree = {key: len(self.incoming[key]) for key in self.nodes}
        remaining = dict(indegree)
        result: list[list[GraphNode]] = []
        placed = 0

        while remaining:
            ready = sorted(k for k, d in remaining.items() if d == 0)
            if not ready:
                raise WorkflowError("Workflow graph contains a cycle.")
            result.append([self.nodes[k] for k in ready])
            placed += len(ready)
            for key in ready:
                del remaining[key]
                for edge in self.outgoing[key]:
                    if edge.target in remaining:
                        remaining[edge.target] -= 1
        if placed != len(self.nodes):  # pragma: no cover - defensive
            raise WorkflowError("Workflow graph contains a cycle.")
        return result


class WorkflowEngine:
    """Executes a :class:`WorkflowGraph`, honouring conditions and loops."""

    def __init__(self, handlers: dict[str, NodeHandler] | None = None) -> None:
        self._handlers = dict(handlers or {})

    def register(self, node_type: str, handler: NodeHandler) -> None:
        self._handlers[node_type] = handler

    def _handler_for(self, node: GraphNode) -> NodeHandler:
        return self._handlers.get(node.type, _default_handler)

    @staticmethod
    def _is_reachable(
        graph: WorkflowGraph,
        node: GraphNode,
        context: dict[str, Any],
        skipped: set[str],
    ) -> tuple[bool, str | None]:
        """Decide whether ``node`` should run.

        A node with no incoming edges is an entry point. Otherwise it runs when
        at least one incoming edge is satisfied *and* its source ran — so a
        pruned branch does not resurrect downstream nodes.
        """
        incoming = graph.incoming.get(node.key)
        if not incoming:
            return True, None

        unmet: list[str] = []
        for edge in incoming:
            if edge.source in skipped:
                unmet.append(f"{edge.source} was skipped")
                continue
            if evaluate_condition(edge.condition, context):
                return True, None
            unmet.append(f"{edge.source} -> {node.key} condition was false")
        return False, "; ".join(unmet)

    async def run(
        self,
        graph: WorkflowGraph,
        context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], list[NodeOutcome]]:
        """Execute ``graph``, returning the final context and per-node outcomes.

        Raises the first node error encountered; the outcomes collected so far
        are attached to the exception's details for the caller to persist.
        """
        run_context: dict[str, Any] = dict(context or {})
        outcomes: list[NodeOutcome] = []
        skipped: set[str] = set()

        for level in graph.levels():
            runnable: list[GraphNode] = []
            for node in level:
                ok, reason = self._is_reachable(graph, node, run_context, skipped)
                if ok:
                    runnable.append(node)
                else:
                    skipped.add(node.key)
                    outcomes.append(
                        NodeOutcome(
                            key=node.key,
                            type=node.type,
                            status=NodeRunStatus.SKIPPED.value,
                            skip_reason=reason,
                        )
                    )

            if not runnable:
                continue

            # Independent nodes run concurrently; one failure stops the run.
            results = await asyncio.gather(
                *(self._run_node(node, run_context) for node in runnable),
                return_exceptions=True,
            )
            for node, result in zip(runnable, results, strict=True):
                if isinstance(result, BaseException):
                    outcomes.append(
                        NodeOutcome(
                            key=node.key,
                            type=node.type,
                            status=NodeRunStatus.FAILED.value,
                            error=str(result),
                        )
                    )
                    raise WorkflowError(
                        f"Node '{node.key}' failed: {result}",
                        # NodeOutcome uses slots, so asdict() rather than
                        # __dict__, which does not exist on a slotted class.
                        details={"outcomes": [asdict(o) for o in outcomes]},
                    ) from result
                outcomes.extend(result)
                run_context[node.key] = result[-1].output if result else None

        return run_context, outcomes

    async def _run_node(
        self, node: GraphNode, context: dict[str, Any]
    ) -> list[NodeOutcome]:
        """Run one node, expanding it if it is a loop."""
        if node.type == NodeKind.LOOP.value:
            return await self._run_loop(node, context)

        handler = self._handler_for(node)
        output = await handler(node, context)
        return [
            NodeOutcome(
                key=node.key,
                type=node.type,
                status=NodeRunStatus.SUCCEEDED.value,
                output=output,
            )
        ]

    async def _run_loop(
        self, node: GraphNode, context: dict[str, Any]
    ) -> list[NodeOutcome]:
        """Run a loop node once per item.

        ``config.over`` is an expression yielding the collection; each pass sees
        the current value as ``item`` and the zero-based index as ``index``.
        """
        source = node.config.get("over")
        if not isinstance(source, str) or not source.strip():
            raise WorkflowError(f"Loop node '{node.key}' needs a config.over expression.")

        collection = evaluate(source, context)
        if collection is None:
            collection = []
        if not isinstance(collection, list | tuple):
            raise WorkflowError(
                f"Loop node '{node.key}' expected a list, got "
                f"{type(collection).__name__}."
            )
        if len(collection) > MAX_LOOP_ITERATIONS:
            raise WorkflowError(
                f"Loop node '{node.key}' exceeds {MAX_LOOP_ITERATIONS} iterations."
            )

        handler = self._handler_for(node)
        outcomes: list[NodeOutcome] = []
        collected: list[Any] = []
        for index, item in enumerate(collection):
            # A copy per pass: a handler mutating its scope must not leak the
            # loop variables into the surrounding run context.
            scope = dict(context)
            scope["item"] = item
            scope["index"] = index
            output = await handler(node, scope)
            collected.append(output)
            outcomes.append(
                NodeOutcome(
                    key=node.key,
                    type=node.type,
                    status=NodeRunStatus.SUCCEEDED.value,
                    iteration=index,
                    output=output,
                )
            )

        if not outcomes:  # an empty collection still records that the node ran
            outcomes.append(
                NodeOutcome(
                    key=node.key,
                    type=node.type,
                    status=NodeRunStatus.SUCCEEDED.value,
                    output=[],
                )
            )
        else:
            outcomes[-1].output = collected
        return outcomes
