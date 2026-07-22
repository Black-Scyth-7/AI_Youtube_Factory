"""Repositories for LLM framework entities."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select

from app.models.llm import (
    Conversation,
    ConversationMessage,
    LLMCostRollup,
    LLMRequest,
    LLMUsageRollup,
    PromptTemplate,
    PromptVersion,
    ProviderConfiguration,
)
from app.repositories.base import BaseRepository


class PromptTemplateRepository(BaseRepository[PromptTemplate]):
    model = PromptTemplate

    async def get_by_name(
        self, organization_id: uuid.UUID, name: str
    ) -> PromptTemplate | None:
        return await self.find_by(organization_id=organization_id, name=name)


class PromptVersionRepository(BaseRepository[PromptVersion]):
    model = PromptVersion

    async def get_version(
        self, template_id: uuid.UUID, version: int
    ) -> PromptVersion | None:
        return await self.find_by(template_id=template_id, version_number=version)

    async def list_for_template(self, template_id: uuid.UUID) -> list[PromptVersion]:
        result = await self.session.execute(
            select(PromptVersion)
            .where(PromptVersion.template_id == template_id)
            .order_by(PromptVersion.version_number.desc())
        )
        return list(result.scalars().all())


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation


class ConversationMessageRepository(BaseRepository[ConversationMessage]):
    model = ConversationMessage

    async def list_for_conversation(
        self, conversation_id: uuid.UUID
    ) -> list[ConversationMessage]:
        result = await self.session.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.sequence.asc())
        )
        return list(result.scalars().all())

    async def next_sequence(self, conversation_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(ConversationMessage.sequence)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.sequence.desc())
            .limit(1)
        )
        return (result.scalar_one_or_none() or 0) + 1


class LLMRequestRepository(BaseRepository[LLMRequest]):
    model = LLMRequest


class LLMUsageRollupRepository(BaseRepository[LLMUsageRollup]):
    model = LLMUsageRollup

    async def get_for(
        self, organization_id: uuid.UUID | None, usage_date: date, model: str
    ) -> LLMUsageRollup | None:
        result = await self.session.execute(
            select(LLMUsageRollup).where(
                LLMUsageRollup.organization_id == organization_id,
                LLMUsageRollup.usage_date == usage_date,
                LLMUsageRollup.model == model,
            )
        )
        return result.scalar_one_or_none()


class LLMCostRollupRepository(BaseRepository[LLMCostRollup]):
    model = LLMCostRollup

    async def get_for(
        self, organization_id: uuid.UUID | None, cost_date: date, model: str
    ) -> LLMCostRollup | None:
        result = await self.session.execute(
            select(LLMCostRollup).where(
                LLMCostRollup.organization_id == organization_id,
                LLMCostRollup.cost_date == cost_date,
                LLMCostRollup.model == model,
            )
        )
        return result.scalar_one_or_none()


class ProviderConfigurationRepository(BaseRepository[ProviderConfiguration]):
    model = ProviderConfiguration
