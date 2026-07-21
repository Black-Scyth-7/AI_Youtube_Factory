"""Repositories for infrastructure entities (feature flags, workflows)."""

from __future__ import annotations

from app.models.infra import FeatureFlag
from app.models.workflow import Workflow, WorkflowExecution
from app.repositories.base import BaseRepository


class FeatureFlagRepository(BaseRepository[FeatureFlag]):
    model = FeatureFlag

    async def get_by_key(self, key: str) -> FeatureFlag | None:
        return await self.find_by(key=key)


class WorkflowRepository(BaseRepository[Workflow]):
    model = Workflow


class WorkflowExecutionRepository(BaseRepository[WorkflowExecution]):
    model = WorkflowExecution
