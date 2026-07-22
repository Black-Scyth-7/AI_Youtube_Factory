"""LLM framework database models.

Prompt templates/versions, conversations/messages/summaries, per-request
accounting (LLMRequest), usage/cost rollups, tool executions, and model/provider
configuration. All use the Phase 03 ``EntityMixin`` conventions.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import EntityMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.types import GUID


class PromptStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class LLMRequestStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STREAMED = "streamed"


# ---- Prompts ------------------------------------------------------------
class PromptTemplate(EntityMixin, Base):
    """A named, versioned prompt owned by an organization."""

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_prompt_org_name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=PromptStatus.DRAFT.value, nullable=False, index=True
    )
    latest_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    versions: Mapped[list[PromptVersion]] = relationship(
        back_populates="template_ref", cascade="all, delete-orphan"
    )


class PromptVersion(EntityMixin, Base):
    """An immutable version of a prompt template."""

    __table_args__ = (
        UniqueConstraint("template_id", "version_number", name="uq_prompt_version"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("prompt_template.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    template: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    examples: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    performance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    token_usage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    template_ref: Mapped[PromptTemplate] = relationship(back_populates="versions")


# ---- Conversations ------------------------------------------------------
class Conversation(EntityMixin, Base):
    """A persisted multi-turn conversation."""

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    system: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    messages: Mapped[list[ConversationMessage]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ConversationMessage(EntityMixin, Base):
    """A single message within a persisted conversation."""

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class ConversationSummary(EntityMixin, Base):
    """A rolling summary compressing older conversation turns."""

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


# ---- Accounting ---------------------------------------------------------
class LLMRequest(EntityMixin, Base):
    """A per-request accounting record (tokens, cost, latency, status)."""

    __tablename__ = "llm_request"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), default=LLMRequestStatus.SUCCEEDED.value, nullable=False, index=True
    )
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )
    latency_ms: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    streamed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class LLMUsageRollup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Daily token-usage rollup per organization/model."""

    __tablename__ = "llm_usage_rollup"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "usage_date", "model", name="uq_usage_org_date_model"
        ),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class LLMCostRollup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Daily cost rollup per organization/model."""

    __tablename__ = "llm_cost_rollup"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "cost_date", "model", name="uq_cost_org_date_model"
        ),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )
    cost_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    input_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )
    output_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )
    total_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )


class ToolExecution(EntityMixin, Base):
    """A record of a tool invocation during an LLM interaction."""

    request_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_error: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ---- Configuration ------------------------------------------------------
class ModelConfiguration(EntityMixin, Base):
    """Administrator-managed per-model configuration overrides."""

    __table_args__ = (
        UniqueConstraint("organization_id", "model", name="uq_model_config_org_model"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    streaming: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    timeout_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    retry_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ProviderConfiguration(EntityMixin, Base):
    """Provider registration with an encrypted secret (API key) at rest."""

    __table_args__ = (
        UniqueConstraint("organization_id", "provider", name="uq_provider_org_slug"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    # Fernet-encrypted secret; never returned in API responses.
    secret_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
