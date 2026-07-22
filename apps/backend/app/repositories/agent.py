"""Repositories for AI agent framework entities."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.agent import (
    Agent,
    AgentConfiguration,
    AgentEvaluation,
    AgentGoal,
    AgentMemoryRecord,
    AgentMetric,
    AgentPlan,
    AgentReflection,
    AgentTaskExecution,
    AgentTaskRecord,
    AgentToolDefinition,
    AgentToolExecution,
    AgentVersion,
    KnowledgeDocument,
    WorkflowRun,
)
from app.repositories.base import BaseRepository


class AgentRepository(BaseRepository[Agent]):
    model = Agent

    async def get_by_slug(
        self, organization_id: uuid.UUID | None, slug: str
    ) -> Agent | None:
        return await self.find_by(organization_id=organization_id, slug=slug)

    async def list_for_org(self, organization_id: uuid.UUID | None) -> list[Agent]:
        result = await self.session.execute(
            select(Agent)
            .where(Agent.organization_id == organization_id)
            .where(Agent.deleted_at.is_(None))
            .order_by(Agent.created_at.desc())
        )
        return list(result.scalars().all())


class AgentVersionRepository(BaseRepository[AgentVersion]):
    model = AgentVersion

    async def list_for_agent(self, agent_id: uuid.UUID) -> list[AgentVersion]:
        result = await self.session.execute(
            select(AgentVersion)
            .where(AgentVersion.agent_id == agent_id)
            .order_by(AgentVersion.created_at.desc())
        )
        return list(result.scalars().all())


class AgentConfigurationRepository(BaseRepository[AgentConfiguration]):
    model = AgentConfiguration


class AgentGoalRepository(BaseRepository[AgentGoal]):
    model = AgentGoal

    async def list_for_org(
        self, organization_id: uuid.UUID, *, limit: int = 100
    ) -> list[AgentGoal]:
        result = await self.session.execute(
            select(AgentGoal)
            .where(AgentGoal.organization_id == organization_id)
            .where(AgentGoal.deleted_at.is_(None))
            .order_by(AgentGoal.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class AgentTaskRepository(BaseRepository[AgentTaskRecord]):
    model = AgentTaskRecord

    async def list_for_run(self, run_id: uuid.UUID) -> list[AgentTaskRecord]:
        result = await self.session.execute(
            select(AgentTaskRecord)
            .where(AgentTaskRecord.run_id == run_id)
            .order_by(AgentTaskRecord.order_index)
        )
        return list(result.scalars().all())

    async def list_for_goal(self, goal_id: uuid.UUID) -> list[AgentTaskRecord]:
        result = await self.session.execute(
            select(AgentTaskRecord)
            .where(AgentTaskRecord.goal_id == goal_id)
            .order_by(AgentTaskRecord.order_index)
        )
        return list(result.scalars().all())


class AgentTaskExecutionRepository(BaseRepository[AgentTaskExecution]):
    model = AgentTaskExecution

    async def list_for_task(self, task_id: uuid.UUID) -> list[AgentTaskExecution]:
        result = await self.session.execute(
            select(AgentTaskExecution)
            .where(AgentTaskExecution.task_id == task_id)
            .order_by(AgentTaskExecution.attempt)
        )
        return list(result.scalars().all())


class AgentMemoryRepository(BaseRepository[AgentMemoryRecord]):
    model = AgentMemoryRecord

    async def list_for_run(self, run_id: uuid.UUID) -> list[AgentMemoryRecord]:
        result = await self.session.execute(
            select(AgentMemoryRecord).where(AgentMemoryRecord.run_id == run_id)
        )
        return list(result.scalars().all())


class KnowledgeDocumentRepository(BaseRepository[KnowledgeDocument]):
    model = KnowledgeDocument

    async def list_for_org(self, organization_id: uuid.UUID) -> list[KnowledgeDocument]:
        result = await self.session.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.organization_id == organization_id)
            .where(KnowledgeDocument.deleted_at.is_(None))
            .order_by(KnowledgeDocument.created_at.desc())
        )
        return list(result.scalars().all())


class AgentToolRepository(BaseRepository[AgentToolDefinition]):
    model = AgentToolDefinition

    async def list_enabled(self) -> list[AgentToolDefinition]:
        result = await self.session.execute(
            select(AgentToolDefinition).where(AgentToolDefinition.enabled.is_(True))
        )
        return list(result.scalars().all())


class AgentToolExecutionRepository(BaseRepository[AgentToolExecution]):
    model = AgentToolExecution

    async def list_for_run(self, run_id: uuid.UUID) -> list[AgentToolExecution]:
        result = await self.session.execute(
            select(AgentToolExecution)
            .where(AgentToolExecution.run_id == run_id)
            .order_by(AgentToolExecution.created_at)
        )
        return list(result.scalars().all())


class AgentReflectionRepository(BaseRepository[AgentReflection]):
    model = AgentReflection

    async def get_for_run(self, run_id: uuid.UUID) -> AgentReflection | None:
        return await self.find_by(run_id=run_id)


class AgentEvaluationRepository(BaseRepository[AgentEvaluation]):
    model = AgentEvaluation

    async def get_for_run(self, run_id: uuid.UUID) -> AgentEvaluation | None:
        return await self.find_by(run_id=run_id)


class AgentPlanRepository(BaseRepository[AgentPlan]):
    model = AgentPlan


class WorkflowRunRepository(BaseRepository[WorkflowRun]):
    model = WorkflowRun


class AgentMetricRepository(BaseRepository[AgentMetric]):
    model = AgentMetric

    async def list_for_org(
        self, organization_id: uuid.UUID, *, limit: int = 500
    ) -> list[AgentMetric]:
        result = await self.session.execute(
            select(AgentMetric)
            .where(AgentMetric.organization_id == organization_id)
            .order_by(AgentMetric.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
