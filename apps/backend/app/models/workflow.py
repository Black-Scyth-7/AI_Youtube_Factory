"""Workflow engine models: workflows, nodes, edges, and executions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.domain_enums import (
    NodeRunStatus,
    TriggerKind,
    WorkflowExecutionStatus,
)
from app.models.mixins import EntityMixin
from app.models.types import GUID


class Workflow(EntityMixin, Base):
    """A reusable workflow definition scoped to a workspace."""

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    nodes: Mapped[list[WorkflowNode]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    edges: Mapped[list[WorkflowEdge]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )


class WorkflowNode(EntityMixin, Base):
    """A node in a workflow graph."""

    __table_args__ = (
        UniqueConstraint("workflow_id", "key", name="uq_workflow_node_key"),
    )

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workflow.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    position: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    workflow: Mapped[Workflow] = relationship(back_populates="nodes")


class WorkflowEdge(EntityMixin, Base):
    """A directed edge connecting two node keys, with an optional condition."""

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workflow.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_key: Mapped[str] = mapped_column(String(128), nullable=False)
    target_key: Mapped[str] = mapped_column(String(128), nullable=False)
    condition: Mapped[str | None] = mapped_column(String(512), nullable=True)

    workflow: Mapped[Workflow] = relationship(back_populates="edges")


class WorkflowTrigger(EntityMixin, Base):
    """What starts a workflow: a person, a clock, or an event."""

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("workflow.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(
        String(16), default=TriggerKind.MANUAL.value, nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    # Five-field cron expression when kind is "schedule".
    cron: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Event name when kind is "event", matched against the internal bus.
    event_type: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # Advanced once fired, so a due trigger is not picked up twice.
    last_fired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class WorkflowNodeExecution(EntityMixin, Base):
    """Per-node outcome of one run — what a visual editor renders."""

    execution_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workflow_execution.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default=NodeRunStatus.PENDING.value, nullable=False, index=True
    )
    # Which loop pass this was; 0 for a node that runs once.
    iteration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set when the node was skipped, naming the condition that excluded it.
    skip_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)


class WorkflowExecution(EntityMixin, Base):
    """A single run of a workflow, with status, context, and logs."""

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("workflow.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=WorkflowExecutionStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    logs: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
