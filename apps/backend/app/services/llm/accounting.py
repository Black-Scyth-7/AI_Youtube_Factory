"""Token accounting and cost tracking service.

Persists a per-request :class:`LLMRequest` record and upserts the daily
usage/cost rollups per organization/model. This is the single place token and
cost data is written, so every LLM call is accounted for consistently.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm.manager import ChatOutcome
from app.core.llm.models import get_model_info
from app.logging import request_id_var
from app.models.llm import (
    LLMCostRollup,
    LLMRequest,
    LLMRequestStatus,
    LLMUsageRollup,
)
from app.repositories.llm import (
    LLMCostRollupRepository,
    LLMRequestRepository,
    LLMUsageRollupRepository,
)


class AccountingService:
    """Records LLM usage and cost."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.requests = LLMRequestRepository(session)
        self.usage = LLMUsageRollupRepository(session)
        self.costs = LLMCostRollupRepository(session)

    async def record(
        self,
        outcome: ChatOutcome,
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        agent_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
        streamed: bool = False,
    ) -> LLMRequest:
        """Write a request record and update the daily rollups."""
        usage = outcome.response.usage
        record = LLMRequest(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            agent_id=agent_id,
            conversation_id=conversation_id,
            provider=outcome.provider,
            model=outcome.response.model,
            status=(
                LLMRequestStatus.STREAMED.value
                if streamed
                else LLMRequestStatus.SUCCEEDED.value
            ),
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=usage.cache_read_tokens,
            total_tokens=usage.total_tokens,
            cost_usd=Decimal(str(outcome.cost_usd)),
            latency_ms=outcome.latency_ms,
            streamed=streamed,
            cache_hit=outcome.cache_hit,
            correlation_id=request_id_var.get(),
        )
        await self.requests.add(record)
        await self._roll_up(
            organization_id, outcome.response.model, usage, outcome.cost_usd
        )
        return record

    async def _roll_up(
        self,
        organization_id: uuid.UUID | None,
        model: str,
        usage: object,
        cost_usd: float,
    ) -> None:
        today = datetime.now(UTC).date()
        info = get_model_info(model)

        usage_row = await self.usage.get_for(organization_id, today, model)
        if usage_row is None:
            usage_row = LLMUsageRollup(
                organization_id=organization_id,
                usage_date=today,
                model=model,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                request_count=0,
            )
            self.session.add(usage_row)
        usage_row.input_tokens += usage.input_tokens  # type: ignore[attr-defined]
        usage_row.output_tokens += usage.output_tokens  # type: ignore[attr-defined]
        usage_row.total_tokens += usage.total_tokens  # type: ignore[attr-defined]
        usage_row.request_count += 1

        cost_row = await self.costs.get_for(organization_id, today, model)
        if cost_row is None:
            cost_row = LLMCostRollup(
                organization_id=organization_id,
                cost_date=today,
                model=model,
                input_cost_usd=Decimal("0"),
                output_cost_usd=Decimal("0"),
                total_cost_usd=Decimal("0"),
            )
            self.session.add(cost_row)
        input_cost = usage.input_tokens / 1_000_000 * info.input_price_per_mtok  # type: ignore[attr-defined]
        output_cost = usage.output_tokens / 1_000_000 * info.output_price_per_mtok  # type: ignore[attr-defined]
        cost_row.input_cost_usd = Decimal(str(cost_row.input_cost_usd)) + Decimal(
            str(input_cost)
        )
        cost_row.output_cost_usd = Decimal(str(cost_row.output_cost_usd)) + Decimal(
            str(output_cost)
        )
        cost_row.total_cost_usd = Decimal(str(cost_row.total_cost_usd)) + Decimal(
            str(cost_usd)
        )
        await self.session.flush()
