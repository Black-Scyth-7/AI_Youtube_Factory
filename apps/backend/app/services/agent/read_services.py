"""Read-oriented agent services.

Thin query services the API uses to surface persisted run artifacts:
reflections, evaluations, task executions, memory, and per-run/aggregate
metrics. Kept together since each is a small read wrapper over its repository.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.monitoring.monitor import MonitorSnapshot, get_agent_monitor
from app.models.agent import (
    AgentEvaluation,
    AgentMetric,
    AgentReflection,
    AgentTaskExecution,
)
from app.repositories.agent import (
    AgentEvaluationRepository,
    AgentMetricRepository,
    AgentReflectionRepository,
    AgentTaskExecutionRepository,
    AgentTaskRepository,
)


class ReflectionService:
    """Reads reflections produced by runs."""

    def __init__(self, session: AsyncSession) -> None:
        self.reflections = AgentReflectionRepository(session)

    async def get_for_run(self, run_id: uuid.UUID) -> AgentReflection | None:
        return await self.reflections.get_for_run(run_id)


class EvaluationService:
    """Reads run evaluations."""

    def __init__(self, session: AsyncSession) -> None:
        self.evaluations = AgentEvaluationRepository(session)

    async def get_for_run(self, run_id: uuid.UUID) -> AgentEvaluation | None:
        return await self.evaluations.get_for_run(run_id)


class ExecutionService:
    """Reads task executions for a run."""

    def __init__(self, session: AsyncSession) -> None:
        self.tasks = AgentTaskRepository(session)
        self.executions = AgentTaskExecutionRepository(session)

    async def executions_for_task(self, task_id: uuid.UUID) -> list[AgentTaskExecution]:
        return await self.executions.list_for_task(task_id)


@dataclass(slots=True)
class MetricsReport:
    """Aggregate metrics for an organization plus the live monitor snapshot."""

    runs: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    success_rate: float
    monitor: MonitorSnapshot


class MetricsService:
    """Aggregates per-run metrics and merges the live monitor snapshot."""

    def __init__(self, session: AsyncSession) -> None:
        self.metrics = AgentMetricRepository(session)

    async def list_for_org(self, organization_id: uuid.UUID) -> list[AgentMetric]:
        return await self.metrics.list_for_org(organization_id)

    async def report(self, organization_id: uuid.UUID) -> MetricsReport:
        rows = await self.metrics.list_for_org(organization_id)
        runs = len(rows)
        tokens = sum(r.total_tokens for r in rows)
        cost = float(sum(r.cost_usd for r in rows))
        latency = sum(r.latency_ms for r in rows)
        succeeded = sum(1 for r in rows if r.goal_status == "completed")
        return MetricsReport(
            runs=runs,
            total_tokens=tokens,
            total_cost_usd=round(cost, 6),
            avg_latency_ms=round(latency / runs, 2) if runs else 0.0,
            success_rate=round(succeeded / runs, 4) if runs else 0.0,
            monitor=get_agent_monitor().snapshot(),
        )
