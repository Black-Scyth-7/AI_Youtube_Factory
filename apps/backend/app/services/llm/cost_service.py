"""Cost and usage reporting service.

Reads the daily rollups to produce usage/cost summaries per organization, date
range, and model — the data behind the usage and cost dashboards.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLMCostRollup, LLMUsageRollup


@dataclass(slots=True)
class UsageSummary:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int


@dataclass(slots=True)
class CostSummary:
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float


class CostService:
    """Aggregates usage and cost rollups."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def usage_summary(
        self,
        *,
        organization_id: uuid.UUID | None,
        start: date,
        end: date,
    ) -> UsageSummary:
        stmt = select(
            func.coalesce(func.sum(LLMUsageRollup.input_tokens), 0),
            func.coalesce(func.sum(LLMUsageRollup.output_tokens), 0),
            func.coalesce(func.sum(LLMUsageRollup.total_tokens), 0),
            func.coalesce(func.sum(LLMUsageRollup.request_count), 0),
        ).where(
            LLMUsageRollup.organization_id == organization_id,
            LLMUsageRollup.usage_date >= start,
            LLMUsageRollup.usage_date <= end,
        )
        row = (await self.session.execute(stmt)).one()
        return UsageSummary(
            input_tokens=int(row[0]),
            output_tokens=int(row[1]),
            total_tokens=int(row[2]),
            request_count=int(row[3]),
        )

    async def cost_summary(
        self,
        *,
        organization_id: uuid.UUID | None,
        start: date,
        end: date,
    ) -> CostSummary:
        stmt = select(
            func.coalesce(func.sum(LLMCostRollup.input_cost_usd), 0),
            func.coalesce(func.sum(LLMCostRollup.output_cost_usd), 0),
            func.coalesce(func.sum(LLMCostRollup.total_cost_usd), 0),
        ).where(
            LLMCostRollup.organization_id == organization_id,
            LLMCostRollup.cost_date >= start,
            LLMCostRollup.cost_date <= end,
        )
        row = (await self.session.execute(stmt)).one()
        return CostSummary(
            input_cost_usd=float(row[0]),
            output_cost_usd=float(row[1]),
            total_cost_usd=float(row[2]),
        )
