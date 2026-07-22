"""AgentService — the application entry point for running agents.

Bridges the in-process agent runtime (:class:`AgentManager` + engine) to
persistence and RBAC. It builds a :class:`Goal`, injects org-scoped knowledge,
runs the agent through the manager, and persists the full run: goal, plan, tasks
and their executions, tool executions, reflection, evaluation, per-run metrics,
and memory. Every AI capability in later phases runs agents through this service.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base.agent import AgentRunResult
from app.agents.base.config import AgentConfig
from app.agents.base.goals import Goal, GoalPriority, SuccessCriterion
from app.agents.manager.manager import AgentManager, get_agent_manager
from app.agents.monitoring.monitor import get_agent_monitor
from app.agents.registry.registry import AgentRegistration
from app.exceptions.base import NotFoundError
from app.models.agent import (
    AgentEvaluation,
    AgentGoal,
    AgentMemoryRecord,
    AgentMetric,
    AgentPlan,
    AgentReflection,
    AgentTaskExecution,
    AgentTaskRecord,
    AgentToolExecution,
)
from app.repositories.agent import (
    AgentEvaluationRepository,
    AgentGoalRepository,
    AgentMemoryRepository,
    AgentMetricRepository,
    AgentPlanRepository,
    AgentReflectionRepository,
    AgentTaskExecutionRepository,
    AgentTaskRepository,
    AgentToolExecutionRepository,
    KnowledgeDocumentRepository,
)
from app.services.agent.knowledge_service import KnowledgeService


@dataclass(slots=True)
class RunSummary:
    """A persisted run's identifiers and headline outcome."""

    run_id: uuid.UUID
    goal_id: uuid.UUID
    agent_slug: str
    state: str
    goal_status: str
    output: str


class AgentService:
    """Runs agents and persists their runs."""

    def __init__(
        self, session: AsyncSession, *, manager: AgentManager | None = None
    ) -> None:
        self.session = session
        self.manager = manager or get_agent_manager()
        self.goals = AgentGoalRepository(session)
        self.tasks = AgentTaskRepository(session)
        self.task_execs = AgentTaskExecutionRepository(session)
        self.tool_execs = AgentToolExecutionRepository(session)
        self.plans = AgentPlanRepository(session)
        self.reflections = AgentReflectionRepository(session)
        self.evaluations = AgentEvaluationRepository(session)
        self.metrics = AgentMetricRepository(session)
        self.memory = AgentMemoryRepository(session)
        self.knowledge_docs = KnowledgeDocumentRepository(session)

    # -- Catalog ----------------------------------------------------------
    def catalog(self) -> list[AgentRegistration]:
        """Return the registered agent catalog (built-in + registered)."""
        return self.manager.registry.all()

    def get_registration(self, slug: str) -> AgentRegistration:
        try:
            return self.manager.registry.get(slug)
        except KeyError as exc:
            raise NotFoundError(f"Agent '{slug}' is not registered.") from exc

    # -- Running ----------------------------------------------------------
    async def run(
        self,
        slug: str,
        objective: str,
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        priority: int = int(GoalPriority.NORMAL),
        constraints: list[str] | None = None,
        expected_output: str | None = None,
        success_criteria: list[str] | None = None,
        model: str | None = None,
        max_iterations: int | None = None,
    ) -> RunSummary:
        """Run an agent for ``objective`` and persist the whole run."""
        self.get_registration(slug)  # validates existence (404 otherwise)

        try:
            goal_priority = GoalPriority(priority)
        except ValueError:
            goal_priority = GoalPriority.NORMAL
        goal = Goal(
            objective=objective,
            priority=goal_priority,
            constraints=constraints or [],
            expected_output=expected_output,
            success_criteria=[
                SuccessCriterion(description=c) for c in success_criteria or []
            ],
        )
        config = AgentConfig()
        if model:
            config.model = model
        if max_iterations is not None:
            config.max_iterations = max_iterations

        knowledge = await KnowledgeService(self.session).build_base(organization_id)

        goal_row = await self.goals.add(
            AgentGoal(
                organization_id=organization_id,
                run_id=None,
                objective=objective,
                priority=priority,
                constraints=constraints or [],
                expected_output=expected_output,
                success_criteria=[{"description": c} for c in success_criteria or []],
                status="active",
                created_by=user_id,
                updated_by=user_id,
            )
        )

        result = await self.manager.run(
            slug,
            goal,
            config=config,
            organization_id=organization_id,
            user_id=user_id,
            knowledge=knowledge,
        )
        run_uuid = uuid.UUID(result.run_id)

        goal_row.run_id = run_uuid
        goal_row.status = result.goal_status.value
        goal_row.result = result.output
        await self._persist_run(
            result,
            goal_id=goal_row.id,
            agent_slug=slug,
            organization_id=organization_id,
            user_id=user_id,
        )
        get_agent_monitor().record_run(result)

        return RunSummary(
            run_id=run_uuid,
            goal_id=goal_row.id,
            agent_slug=slug,
            state=result.state.value,
            goal_status=result.goal_status.value,
            output=result.output,
        )

    async def _persist_run(
        self,
        result: AgentRunResult,
        *,
        goal_id: uuid.UUID,
        agent_slug: str,
        organization_id: uuid.UUID | None,
        user_id: uuid.UUID | None,
    ) -> None:
        run_uuid = uuid.UUID(result.run_id)

        # Plan
        await self.plans.add(
            AgentPlan(
                goal_id=goal_id,
                run_id=run_uuid,
                rationale=str(result.reasoning_log[0] if result.reasoning_log else "")[
                    :2000
                ],
                outline=[t.description for t in result.graph.tasks][:20],
                task_count=len(result.graph.tasks),
                created_by=user_id,
                updated_by=user_id,
            )
        )

        # Tasks + executions + tool executions
        for index, task in enumerate(result.graph.topological_order()):
            task_row = await self.tasks.add(
                AgentTaskRecord(
                    goal_id=goal_id,
                    run_id=run_uuid,
                    key=task.key,
                    description=task.description,
                    kind=task.kind.value,
                    status=task.status.value,
                    priority=int(task.priority),
                    order_index=index,
                    depends_on=task.depends_on,
                    attempts=task.attempts,
                    progress=task.progress,
                    max_retries=task.max_retries,
                    error=task.error,
                    result=str(task.result) if task.result is not None else None,
                    artifacts=task.artifacts,
                    created_by=user_id,
                    updated_by=user_id,
                )
            )
            await self.task_execs.add(
                AgentTaskExecution(
                    task_id=task_row.id,
                    attempt=task.attempts,
                    status=task.status.value,
                    output=str(task.result) if task.result is not None else "",
                    error=task.error,
                    created_by=user_id,
                    updated_by=user_id,
                )
            )
            for artifact in task.artifacts:
                if artifact.get("type") == "tool":
                    await self.tool_execs.add(
                        AgentToolExecution(
                            run_id=run_uuid,
                            task_id=task_row.id,
                            tool_name=str(artifact.get("tool", "")),
                            arguments={},
                            output=str(artifact.get("output", "")),
                            success=bool(artifact.get("success", True)),
                            error=artifact.get("error"),
                            created_by=user_id,
                            updated_by=user_id,
                        )
                    )

        # Reflection
        if result.reflection is not None:
            await self.reflections.add(
                AgentReflection(
                    run_id=run_uuid,
                    summary=result.reflection.summary,
                    mistakes=result.reflection.mistakes,
                    lessons=result.reflection.lessons,
                    improvements=result.reflection.improvements,
                    created_by=user_id,
                    updated_by=user_id,
                )
            )

        # Evaluation
        if result.evaluation is not None:
            ev = result.evaluation
            await self.evaluations.add(
                AgentEvaluation(
                    run_id=run_uuid,
                    correctness=ev.correctness,
                    completeness=ev.completeness,
                    cost=ev.cost,
                    latency=ev.latency,
                    quality=ev.quality,
                    confidence=ev.confidence,
                    overall=ev.overall,
                    notes=ev.notes,
                    created_by=user_id,
                    updated_by=user_id,
                )
            )

        # Metric snapshot
        m = result.metrics
        await self.metrics.add(
            AgentMetric(
                organization_id=organization_id,
                run_id=run_uuid,
                agent_slug=agent_slug,
                state=result.state.value,
                goal_status=result.goal_status.value,
                input_tokens=m.input_tokens,
                output_tokens=m.output_tokens,
                total_tokens=m.total_tokens,
                cost_usd=Decimal(str(round(m.cost_usd, 6))),
                latency_ms=m.latency_ms,
                tasks_total=m.tasks_total,
                tasks_succeeded=m.tasks_succeeded,
                tasks_failed=m.tasks_failed,
                tool_calls=m.tool_calls,
                retries=m.retries,
                created_by=user_id,
                updated_by=user_id,
            )
        )

    # -- Reading run artifacts -------------------------------------------
    async def get_goal(self, goal_id: uuid.UUID) -> AgentGoal:
        goal = await self.goals.get(goal_id)
        if goal is None or goal.deleted_at is not None:
            raise NotFoundError("Goal not found.")
        return goal

    async def run_tasks(self, run_id: uuid.UUID) -> list[AgentTaskRecord]:
        return await self.tasks.list_for_run(run_id)

    async def run_tool_executions(self, run_id: uuid.UUID) -> list[AgentToolExecution]:
        return await self.tool_execs.list_for_run(run_id)

    async def run_memory(self, run_id: uuid.UUID) -> list[AgentMemoryRecord]:
        return await self.memory.list_for_run(run_id)
