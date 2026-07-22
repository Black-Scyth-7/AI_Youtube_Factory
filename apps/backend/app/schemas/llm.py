"""Request/response schemas for the LLM API."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageIn(BaseModel):
    role: str = Field(pattern="^(user|assistant|system|developer|tool)$")
    content: str


class ChatRequestIn(BaseModel):
    messages: list[ChatMessageIn] = Field(min_length=1)
    model: str | None = None
    system: str | None = None
    max_tokens: int | None = Field(default=None, ge=1, le=200_000)
    provider: str | None = None
    organization_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None


class UsageOut(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cache_read_tokens: int = 0


class ChatResponseOut(BaseModel):
    content: str
    model: str
    provider: str
    stop_reason: str
    usage: UsageOut
    cost_usd: float
    latency_ms: float
    cache_hit: bool


class ModelOut(BaseModel):
    id: str
    display_name: str
    context_window: int
    max_output: int
    input_price_per_mtok: float
    output_price_per_mtok: float
    supports_tools: bool
    supports_streaming: bool


class ProviderHealthOut(BaseModel):
    provider: str
    healthy: bool


class PromptVariableIn(BaseModel):
    name: str
    required: bool = True
    default: Any = None
    description: str | None = None


class PromptCreateIn(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    template: str
    category: str | None = None
    description: str | None = None
    variables: list[PromptVariableIn] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class PromptVersionIn(BaseModel):
    template: str
    variables: list[PromptVariableIn] = Field(default_factory=list)


class PromptRenderIn(BaseModel):
    context: dict[str, Any] = Field(default_factory=dict)
    version: int | None = None


class PromptRenderOut(BaseModel):
    rendered: str


class PromptTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    category: str | None
    status: str
    latest_version: int
    created_at: datetime


class ConversationCreateIn(BaseModel):
    organization_id: uuid.UUID
    model: str | None = None
    system: str | None = None
    title: str | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    title: str | None
    model: str
    created_at: datetime


class ConversationMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence: int
    role: str
    content: str
    tokens: int


class UsageSummaryOut(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_count: int


class CostSummaryOut(BaseModel):
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float


class ToolSchemaOut(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class DateRangeParams(BaseModel):
    start: date
    end: date
