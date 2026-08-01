"""Unit tests for the workflow expression evaluator and graph engine.

Both are database-free, so these run as plain unit tests.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from app.core.workflow import (
    MAX_EXPONENT,
    ExpressionError,
    GraphEdge,
    GraphNode,
    WorkflowEngine,
    WorkflowGraph,
    evaluate,
    evaluate_condition,
)
from app.exceptions.base import WorkflowError
from app.models.domain_enums import NodeRunStatus


# -- Expression evaluation ----------------------------------------------------
@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("1 + 1", 2),
        ("10 / 4", 2.5),
        ("7 // 2", 3),
        ("7 % 2", 1),
        ("2 ** 8", 256),
        ("-5", -5),
        ("not 0", True),
        ("[1, 2, 3]", [1, 2, 3]),
        ("1 < 2 < 3", True),
        ("1 < 2 < 0", False),
        ("'a' in ['a', 'b']", True),
        ("'z' not in ['a']", True),
    ],
)
def test_arithmetic_and_comparisons(expression: str, expected: object) -> None:
    assert evaluate(expression) == expected


def test_names_resolve_from_context() -> None:
    context = {"score": 7, "tags": ["a", "b"], "nested": {"ok": True}}
    assert evaluate("score > 5", context) is True
    assert evaluate("'a' in tags", context) is True
    assert evaluate("nested['ok']", context) is True


def test_unknown_names_are_none_rather_than_an_error() -> None:
    """A condition may reference a value an earlier node did not set."""
    assert evaluate("missing", {}) is None
    assert evaluate_condition("missing == None", {}) is True


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('echo hi')",
        "().__class__.__bases__",
        "open('/etc/passwd')",
        "[x for x in range(3)]",
        "lambda: 1",
        "print('hi')",
        "os.system('ls')",
    ],
)
def test_dangerous_constructs_are_refused(expression: str) -> None:
    """Calls, attribute access and comprehensions must all be rejected."""
    with pytest.raises(ExpressionError):
        evaluate(expression)


def test_exponent_is_bounded() -> None:
    """The DoS that an eval-based allow-list let through."""
    start = time.time()
    with pytest.raises(ExpressionError, match="Exponent"):
        evaluate("9**9**9**9")
    assert time.time() - start < 1.0  # refused immediately, not computed
    assert evaluate(f"2 ** {MAX_EXPONENT}") == 2**MAX_EXPONENT


def test_division_by_zero_is_an_expression_error() -> None:
    with pytest.raises(ExpressionError, match="zero"):
        evaluate("1 / 0")


def test_overlong_and_overnested_expressions_are_refused() -> None:
    with pytest.raises(ExpressionError, match="too long"):
        evaluate("1 + " * 400 + "1")
    # Parentheses do not create AST nodes — "((1))" parses to a bare Constant —
    # so depth has to come from real nesting such as chained unary operators.
    with pytest.raises(ExpressionError, match="deeply"):
        evaluate("-" * 40 + "1")


def test_syntax_errors_are_reported_cleanly() -> None:
    with pytest.raises(ExpressionError, match="Invalid expression"):
        evaluate("1 +")


def test_blank_condition_is_true() -> None:
    assert evaluate_condition(None, {}) is True
    assert evaluate_condition("   ", {}) is True


# -- Graph validation ---------------------------------------------------------
def test_duplicate_node_keys_are_refused() -> None:
    with pytest.raises(WorkflowError, match="Duplicate"):
        WorkflowGraph([GraphNode("a", "task"), GraphNode("a", "task")], [])


def test_edge_to_an_unknown_node_is_refused() -> None:
    with pytest.raises(WorkflowError, match="unknown node"):
        WorkflowGraph([GraphNode("a", "task")], [GraphEdge("a", "ghost")])


def test_cycles_are_detected() -> None:
    graph = WorkflowGraph(
        [GraphNode("a", "task"), GraphNode("b", "task")],
        [GraphEdge("a", "b"), GraphEdge("b", "a")],
    )
    with pytest.raises(WorkflowError, match="cycle"):
        graph.levels()


def test_levels_group_independent_nodes() -> None:
    graph = WorkflowGraph(
        [GraphNode(k, "task") for k in ("start", "a", "b", "end")],
        [
            GraphEdge("start", "a"),
            GraphEdge("start", "b"),
            GraphEdge("a", "end"),
            GraphEdge("b", "end"),
        ],
    )
    levels = [[n.key for n in level] for level in graph.levels()]
    assert levels == [["start"], ["a", "b"], ["end"]]


# -- Execution ----------------------------------------------------------------
@pytest.mark.asyncio
async def test_runs_every_node_when_unconditional() -> None:
    ran: list[str] = []

    async def handler(node: GraphNode, context: dict[str, Any]) -> Any:
        ran.append(node.key)
        return node.key

    engine = WorkflowEngine({"task": handler})
    graph = WorkflowGraph(
        [GraphNode("a", "task"), GraphNode("b", "task")], [GraphEdge("a", "b")]
    )
    context, outcomes = await engine.run(graph)

    assert ran == ["a", "b"]
    assert context["a"] == "a"
    assert all(o.status == NodeRunStatus.SUCCEEDED.value for o in outcomes)


@pytest.mark.asyncio
async def test_a_false_condition_prunes_the_branch() -> None:
    """The behaviour the Phase 03 walk was missing entirely."""
    ran: list[str] = []

    async def handler(node: GraphNode, context: dict[str, Any]) -> Any:
        ran.append(node.key)
        return {"score": 3}

    engine = WorkflowEngine({"task": handler})
    graph = WorkflowGraph(
        [GraphNode("start", "task"), GraphNode("high", "task"), GraphNode("low", "task")],
        [
            GraphEdge("start", "high", condition="start['score'] > 10"),
            GraphEdge("start", "low", condition="start['score'] <= 10"),
        ],
    )
    _, outcomes = await engine.run(graph)

    assert "low" in ran and "high" not in ran
    by_key = {o.key: o for o in outcomes}
    assert by_key["high"].status == NodeRunStatus.SKIPPED.value
    assert by_key["high"].skip_reason is not None
    assert by_key["low"].status == NodeRunStatus.SUCCEEDED.value


@pytest.mark.asyncio
async def test_skipping_propagates_downstream() -> None:
    """A node whose only source was skipped must not run."""

    async def handler(node: GraphNode, context: dict[str, Any]) -> Any:
        return 1

    engine = WorkflowEngine({"task": handler})
    graph = WorkflowGraph(
        [GraphNode(k, "task") for k in ("start", "mid", "end")],
        [GraphEdge("start", "mid", condition="False"), GraphEdge("mid", "end")],
    )
    _, outcomes = await engine.run(graph)

    by_key = {o.key: o for o in outcomes}
    assert by_key["mid"].status == NodeRunStatus.SKIPPED.value
    assert by_key["end"].status == NodeRunStatus.SKIPPED.value


@pytest.mark.asyncio
async def test_a_merge_runs_when_any_branch_survives() -> None:
    async def handler(node: GraphNode, context: dict[str, Any]) -> Any:
        return node.key

    engine = WorkflowEngine({"task": handler})
    graph = WorkflowGraph(
        [GraphNode(k, "task") for k in ("start", "a", "b", "merge")],
        [
            GraphEdge("start", "a", condition="False"),
            GraphEdge("start", "b"),
            GraphEdge("a", "merge"),
            GraphEdge("b", "merge"),
        ],
    )
    _, outcomes = await engine.run(graph)

    by_key = {o.key: o for o in outcomes}
    assert by_key["a"].status == NodeRunStatus.SKIPPED.value
    assert by_key["merge"].status == NodeRunStatus.SUCCEEDED.value


@pytest.mark.asyncio
async def test_independent_nodes_run_concurrently() -> None:
    """Two 100ms nodes on the same level should overlap, not queue."""

    async def slow(node: GraphNode, context: dict[str, Any]) -> Any:
        await asyncio.sleep(0.1)
        return node.key

    engine = WorkflowEngine({"task": slow})
    graph = WorkflowGraph(
        [GraphNode(k, "task") for k in ("start", "a", "b")],
        [GraphEdge("start", "a"), GraphEdge("start", "b")],
    )
    started = time.perf_counter()
    await engine.run(graph)
    elapsed = time.perf_counter() - started

    # Sequential would be ~0.3s; concurrent is ~0.2s (start, then a+b together).
    assert elapsed < 0.28, f"took {elapsed:.2f}s — nodes did not overlap"


@pytest.mark.asyncio
async def test_loop_runs_once_per_item() -> None:
    seen: list[Any] = []

    async def handler(node: GraphNode, context: dict[str, Any]) -> Any:
        seen.append((context["index"], context["item"]))
        return context["item"] * 2

    engine = WorkflowEngine({"loop": handler})
    graph = WorkflowGraph([GraphNode("each", "loop", config={"over": "numbers"})], [])
    context, outcomes = await engine.run(graph, {"numbers": [1, 2, 3]})

    assert seen == [(0, 1), (1, 2), (2, 3)]
    assert context["each"] == [2, 4, 6]
    assert [o.iteration for o in outcomes] == [0, 1, 2]


@pytest.mark.asyncio
async def test_loop_variables_do_not_leak_into_the_run_context() -> None:
    async def handler(node: GraphNode, context: dict[str, Any]) -> Any:
        return context["item"]

    engine = WorkflowEngine({"loop": handler})
    graph = WorkflowGraph([GraphNode("each", "loop", config={"over": "xs"})], [])
    context, _ = await engine.run(graph, {"xs": [1]})

    assert "item" not in context and "index" not in context


@pytest.mark.asyncio
async def test_loop_over_an_empty_list_still_records_the_node() -> None:
    engine = WorkflowEngine()
    graph = WorkflowGraph([GraphNode("each", "loop", config={"over": "xs"})], [])
    _, outcomes = await engine.run(graph, {"xs": []})

    assert len(outcomes) == 1
    assert outcomes[0].status == NodeRunStatus.SUCCEEDED.value


@pytest.mark.asyncio
async def test_loop_needs_a_collection_and_a_source() -> None:
    engine = WorkflowEngine()
    with pytest.raises(WorkflowError, match=r"config.over"):
        await engine.run(WorkflowGraph([GraphNode("bad", "loop")], []))

    graph = WorkflowGraph([GraphNode("bad", "loop", config={"over": "x"})], [])
    with pytest.raises(WorkflowError, match="expected a list"):
        await engine.run(graph, {"x": 5})


@pytest.mark.asyncio
async def test_loop_iterations_are_capped() -> None:
    engine = WorkflowEngine()
    graph = WorkflowGraph([GraphNode("each", "loop", config={"over": "xs"})], [])
    with pytest.raises(WorkflowError, match="exceeds"):
        await engine.run(graph, {"xs": list(range(5000))})


@pytest.mark.asyncio
async def test_a_failing_node_stops_the_run_and_reports_outcomes() -> None:
    async def boom(node: GraphNode, context: dict[str, Any]) -> Any:
        raise RuntimeError("handler exploded")

    engine = WorkflowEngine({"task": boom})
    graph = WorkflowGraph([GraphNode("a", "task")], [])

    with pytest.raises(WorkflowError) as info:
        await engine.run(graph)
    outcomes = (info.value.details or {}).get("outcomes", [])
    assert outcomes and outcomes[0]["status"] == NodeRunStatus.FAILED.value
    assert "handler exploded" in outcomes[0]["error"]


@pytest.mark.asyncio
async def test_unregistered_node_types_fall_back_to_a_default() -> None:
    engine = WorkflowEngine()
    graph = WorkflowGraph([GraphNode("a", "mystery")], [])
    context, outcomes = await engine.run(graph)

    assert outcomes[0].status == NodeRunStatus.SUCCEEDED.value
    assert context["a"] == {"node": "a", "type": "mystery"}
