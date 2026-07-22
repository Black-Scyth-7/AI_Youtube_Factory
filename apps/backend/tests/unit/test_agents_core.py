"""Unit tests for the agent framework core (offline, mock provider)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.agents.base.goals import Goal, GoalStatus, SuccessCriterion
from app.agents.base.lifecycle import AgentState, can_transition
from app.agents.base.tasks import AgentTask, TaskGraph, TaskStatus
from app.agents.manager.manager import AgentManager
from app.agents.policies.policies import (
    AgentPolicy,
    PolicyEnforcer,
    PolicyViolationError,
)
from app.agents.registry.registry import AgentRegistry
from app.agents.scheduler.scheduler import (
    ScheduledJob,
    ScheduleKind,
    cron_matches,
)
from app.agents.tools.builtins import CalculatorTool, default_tools
from app.agents.tools.registry import AgentToolRegistry
from app.agents.workflows.workflow import AgentWorkflow, WorkflowStep


# -- Task graph ----------------------------------------------------------
def test_task_graph_topological_order() -> None:
    graph = TaskGraph(
        [
            AgentTask(description="a", key="a"),
            AgentTask(description="b", key="b", depends_on=["a"]),
            AgentTask(description="c", key="c", depends_on=["b"]),
        ]
    )
    order = [t.key for t in graph.topological_order()]
    assert order == ["a", "b", "c"]


def test_task_graph_detects_cycle() -> None:
    graph = TaskGraph(
        [
            AgentTask(description="a", key="a", depends_on=["b"]),
            AgentTask(description="b", key="b", depends_on=["a"]),
        ]
    )
    with pytest.raises(ValueError, match="cycle"):
        graph.topological_order()


def test_task_graph_ready_respects_dependencies() -> None:
    a = AgentTask(description="a", key="a")
    b = AgentTask(description="b", key="b", depends_on=["a"])
    graph = TaskGraph([a, b])
    assert [t.key for t in graph.ready()] == ["a"]
    a.status = TaskStatus.SUCCEEDED
    assert [t.key for t in graph.ready()] == ["b"]


# -- Lifecycle -----------------------------------------------------------
def test_lifecycle_transitions() -> None:
    assert can_transition(AgentState.CREATED, AgentState.INITIALIZING)
    assert not can_transition(AgentState.COMPLETED, AgentState.EXECUTING)


# -- Tools ---------------------------------------------------------------
@pytest.mark.asyncio
async def test_calculator_tool() -> None:
    registry = AgentToolRegistry()
    registry.register(CalculatorTool())
    outcome = await registry.run("calculator", {"expression": "2 + 3 * 4"})
    assert outcome.success
    assert outcome.output == "14"


@pytest.mark.asyncio
async def test_calculator_rejects_unsafe() -> None:
    outcome = await AgentToolRegistry({t.name: t for t in default_tools()}).run(
        "calculator", {"expression": "__import__('os')"}
    )
    assert not outcome.success


def test_default_tools_present() -> None:
    names = {t.name for t in default_tools()}
    assert {"current_time", "calculator", "uuid_generator"} <= names


# -- Policies ------------------------------------------------------------
def test_policy_forbids_and_limits() -> None:
    enforcer = PolicyEnforcer(
        AgentPolicy(forbidden_tools=frozenset({"danger"}), max_cost_usd=0.01)
    )
    with pytest.raises(PolicyViolationError):
        enforcer.check_tool("danger")
    with pytest.raises(PolicyViolationError):
        enforcer.add_usage(cost_usd=1.0, tokens=1)


# -- Scheduler -----------------------------------------------------------
def test_cron_matches() -> None:
    moment = datetime(2026, 7, 22, 9, 0, tzinfo=UTC)
    assert cron_matches("0 9 * * *", moment)
    assert not cron_matches("30 9 * * *", moment)
    assert cron_matches("*/15 * * * *", moment)


def test_recurring_job_due() -> None:
    job = ScheduledJob(
        agent_slug="echo",
        objective="x",
        kind=ScheduleKind.RECURRING,
        interval_seconds=60,
    )
    assert job.is_due(datetime.now(UTC))


# -- Registry ------------------------------------------------------------
def test_registry_discovery() -> None:
    registry = AgentRegistry()
    from app.agents.examples.echo_agent import EchoAgent

    registry.register(EchoAgent)
    assert registry.get("echo").slug == "echo"
    assert registry.discover(capability="echo")


# -- Workflow ------------------------------------------------------------
@pytest.mark.asyncio
async def test_workflow_sequential_and_parallel() -> None:
    async def inc(ctx: dict[str, object]) -> int:
        return 1

    wf = AgentWorkflow("t")
    wf.add(WorkflowStep("s1", inc))
    wf.add(WorkflowStep("p1", inc, parallel_group="g"))
    wf.add(WorkflowStep("p2", inc, parallel_group="g"))
    result = await wf.run({})
    assert result.completed
    assert result.context["s1"] == 1
    assert result.context["p1"] == 1 and result.context["p2"] == 1


@pytest.mark.asyncio
async def test_workflow_conditional_skip() -> None:
    async def act(ctx: dict[str, object]) -> str:
        return "ran"

    wf = AgentWorkflow("t")
    wf.add(WorkflowStep("skipped", act, condition=lambda _: False))
    result = await wf.run({})
    assert result.steps[0].status.value == "skipped"


# -- End-to-end agent run (mock provider) --------------------------------
@pytest.mark.asyncio
async def test_agent_run_completes() -> None:
    manager = AgentManager()
    goal = Goal(
        objective="Summarize testing best practices",
        success_criteria=[SuccessCriterion(description="cover unit tests")],
    )
    result = await manager.run("assistant", goal)
    assert result.goal_status == GoalStatus.COMPLETED
    assert result.metrics.tasks_total >= 1
    assert result.evaluation is not None
    assert result.evaluation.overall > 0
    assert result.output


@pytest.mark.asyncio
async def test_agent_reflection_generates_lessons() -> None:
    manager = AgentManager()
    result = await manager.run("assistant", Goal(objective="Explain caching"))
    assert result.reflection is not None
    assert result.reflection.summary
