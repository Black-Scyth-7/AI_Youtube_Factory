"""AI agent framework database models.

Persistence for the Phase 05 agent platform: agents and their versions/configs,
goals and tasks (with executions), agent memory and knowledge documents, tool
definitions and executions, reflections, evaluations, plans, workflow runs, and
per-run metrics. All use the Phase 03 :class:`EntityMixin` conventions.

Table and class names are prefixed to avoid colliding with the Phase 04 LLM
``ToolExecution``/``Tool`` names and the runtime ``Goal``/``Task`` dataclasses.
Business fields never use the name ``version`` (reserved by ``EntityMixin`` for
optimistic locking) — agent version labels are stored as ``version_label``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
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
from app.models.mixins import EntityMixin
from app.models.types import GUID


# ---- Agents -------------------------------------------------------------
class Agent(EntityMixin, Base):
    """A persisted, discoverable agent definition."""

    __tablename__ = "agent"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_agent_org_slug"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    default_version_label: Mapped[str] = mapped_column(
        String(32), default="1.0.0", nullable=False
    )
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    versions: Mapped[list[AgentVersion]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )


class AgentVersion(EntityMixin, Base):
    """An immutable version of an agent's configuration."""

    __tablename__ = "agent_version"
    __table_args__ = (
        UniqueConstraint("agent_id", "version_label", name="uq_agent_version"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agent.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_label: Mapped[str] = mapped_column(String(32), nullable=False)
    changelog: Mapped[str] = mapped_column(Text, default="", nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    agent: Mapped[Agent] = relationship(back_populates="versions")


class AgentConfiguration(EntityMixin, Base):
    """A named, reusable configuration for running an agent."""

    __tablename__ = "agent_configuration"

    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agent.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128), default="default", nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096, nullable=False)
    max_iterations: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    reflection_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    evaluation_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    policy: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    extra: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


# ---- Goals & tasks ------------------------------------------------------
class AgentGoal(EntityMixin, Base):
    """A goal submitted to an agent."""

    __tablename__ = "agent_goal"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agent.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    constraints: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    expected_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    success_criteria: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False, index=True
    )
    result: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentTaskRecord(EntityMixin, Base):
    """A planned task belonging to a goal/run."""

    __tablename__ = "agent_task"

    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("agent_goal.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="reason", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False, index=True
    )
    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    depends_on: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifacts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )


class AgentTaskExecution(EntityMixin, Base):
    """A single execution attempt of a task."""

    __tablename__ = "agent_task_execution"

    task_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("agent_task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


# ---- Memory & knowledge -------------------------------------------------
class AgentMemoryRecord(EntityMixin, Base):
    """A persisted agent memory entry (scoped key/value)."""

    __tablename__ = "agent_memory"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agent.id", ondelete="CASCADE"), nullable=True, index=True
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(64), default="agent", nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class KnowledgeDocument(EntityMixin, Base):
    """A knowledge document an agent can consult."""

    __tablename__ = "knowledge_document"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agent.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="fact", nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source: Mapped[str | None] = mapped_column(String(512), nullable=True)


# ---- Tools --------------------------------------------------------------
class AgentToolDefinition(EntityMixin, Base):
    """A registered tool definition available to agents."""

    __tablename__ = "agent_tool"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_agent_tool_name"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    input_schema: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    category: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    mutating: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AgentToolExecution(EntityMixin, Base):
    """An audit record of a tool execution by an agent."""

    __tablename__ = "agent_tool_execution"

    run_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


# ---- Reflection, evaluation, plans --------------------------------------
class AgentReflection(EntityMixin, Base):
    """A reflection produced after a run."""

    __tablename__ = "agent_reflection"

    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agent.id", ondelete="SET NULL"), nullable=True, index=True
    )
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    mistakes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    lessons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    improvements: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class AgentEvaluation(EntityMixin, Base):
    """A per-run evaluation with dimensional scores."""

    __tablename__ = "agent_evaluation"

    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agent.id", ondelete="SET NULL"), nullable=True, index=True
    )
    correctness: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completeness: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    quality: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    overall: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    notes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class AgentPlan(EntityMixin, Base):
    """A recorded plan (rationale + outline + task count) for a run."""

    __tablename__ = "agent_plan"

    goal_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("agent_goal.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    outline: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    task_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class WorkflowRun(EntityMixin, Base):
    """A recorded agent workflow execution."""

    __tablename__ = "agent_workflow_run"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agent.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), default="workflow", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class AgentMetric(EntityMixin, Base):
    """A per-run metrics snapshot for monitoring and dashboards."""

    __tablename__ = "agent_metric"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), nullable=True, index=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("agent.id", ondelete="SET NULL"), nullable=True, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    agent_slug: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    goal_status: Mapped[str] = mapped_column(String(32), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tasks_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tasks_succeeded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tasks_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retries: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
