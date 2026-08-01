"""Agent framework schema.

Agents and versions, goals, plans, tasks and executions, reflections,
evaluations, memories, knowledge, tools, and metrics.

The DDL here is explicit and frozen: it describes the schema as of this
revision and must never be regenerated from the ORM metadata. These migrations
used to call ``Base.metadata.create_all()``, which had two consequences. Each
migration produced whatever the models happened to look like when it ran, so
the history described no particular schema; and because ``create_all`` only
creates missing tables, no migration could ever alter an existing one — a
column added to a model reached a fresh database and silently never reached a
deployed one.

``test_migrations.py`` compares the schema these produce against the ORM
metadata, so a model change without a matching migration fails the suite.

Revision ID: 0004_agent
Revises: 0003_llm
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import app.models.types
import sqlalchemy as sa
from alembic import op

revision: str = "0004_agent"
down_revision: str | None = "0003_llm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the tables introduced by this revision."""
    op.create_table(
        "agent_tool",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("mutating", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("is_builtin", sa.Boolean(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_tool")),
        sa.UniqueConstraint("organization_id", "name", name="uq_agent_tool_name"),
    )
    op.create_index(
        op.f("ix_agent_tool_deleted_at"), "agent_tool", ["deleted_at"], unique=False
    )
    op.create_index(op.f("ix_agent_tool_name"), "agent_tool", ["name"], unique=False)
    op.create_index(
        op.f("ix_agent_tool_organization_id"),
        "agent_tool",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "agent_tool_execution",
        sa.Column("run_id", app.models.types.GUID(), nullable=True),
        sa.Column("task_id", app.models.types.GUID(), nullable=True),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("output", sa.Text(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_tool_execution")),
    )
    op.create_index(
        op.f("ix_agent_tool_execution_deleted_at"),
        "agent_tool_execution",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_tool_execution_run_id"),
        "agent_tool_execution",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_tool_execution_task_id"),
        "agent_tool_execution",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_tool_execution_tool_name"),
        "agent_tool_execution",
        ["tool_name"],
        unique=False,
    )

    op.create_table(
        "agent",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("default_version_label", sa.String(length=32), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_agent_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent")),
        sa.UniqueConstraint("organization_id", "slug", name="uq_agent_org_slug"),
    )
    op.create_index(op.f("ix_agent_deleted_at"), "agent", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_agent_organization_id"), "agent", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_agent_slug"), "agent", ["slug"], unique=False)

    op.create_table(
        "agent_configuration",
        sa.Column("agent_id", app.models.types.GUID(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("max_tokens", sa.Integer(), nullable=False),
        sa.Column("max_iterations", sa.Integer(), nullable=False),
        sa.Column("reflection_enabled", sa.Boolean(), nullable=False),
        sa.Column("evaluation_enabled", sa.Boolean(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("policy", sa.JSON(), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_agent_configuration_agent_id_agent"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_configuration")),
    )
    op.create_index(
        op.f("ix_agent_configuration_agent_id"),
        "agent_configuration",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_configuration_deleted_at"),
        "agent_configuration",
        ["deleted_at"],
        unique=False,
    )

    op.create_table(
        "agent_evaluation",
        sa.Column("run_id", app.models.types.GUID(), nullable=False),
        sa.Column("agent_id", app.models.types.GUID(), nullable=True),
        sa.Column("correctness", sa.Float(), nullable=False),
        sa.Column("completeness", sa.Float(), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False),
        sa.Column("latency", sa.Float(), nullable=False),
        sa.Column("quality", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("overall", sa.Float(), nullable=False),
        sa.Column("notes", sa.JSON(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_agent_evaluation_agent_id_agent"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_evaluation")),
    )
    op.create_index(
        op.f("ix_agent_evaluation_agent_id"),
        "agent_evaluation",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_evaluation_deleted_at"),
        "agent_evaluation",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_evaluation_run_id"), "agent_evaluation", ["run_id"], unique=False
    )

    op.create_table(
        "agent_goal",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("agent_id", app.models.types.GUID(), nullable=True),
        sa.Column("run_id", app.models.types.GUID(), nullable=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=True),
        sa.Column("success_criteria", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_agent_goal_agent_id_agent"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_agent_goal_organization_id_organization"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_goal")),
    )
    op.create_index(
        op.f("ix_agent_goal_agent_id"), "agent_goal", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_agent_goal_deleted_at"), "agent_goal", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_agent_goal_organization_id"),
        "agent_goal",
        ["organization_id"],
        unique=False,
    )
    op.create_index(op.f("ix_agent_goal_run_id"), "agent_goal", ["run_id"], unique=False)
    op.create_index(op.f("ix_agent_goal_status"), "agent_goal", ["status"], unique=False)

    op.create_table(
        "agent_memory",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("agent_id", app.models.types.GUID(), nullable=True),
        sa.Column("run_id", app.models.types.GUID(), nullable=True),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_agent_memory_agent_id_agent"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_memory")),
    )
    op.create_index(
        op.f("ix_agent_memory_agent_id"), "agent_memory", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_agent_memory_deleted_at"), "agent_memory", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_agent_memory_organization_id"),
        "agent_memory",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_memory_run_id"), "agent_memory", ["run_id"], unique=False
    )

    op.create_table(
        "agent_metric",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("agent_id", app.models.types.GUID(), nullable=True),
        sa.Column("run_id", app.models.types.GUID(), nullable=False),
        sa.Column("agent_slug", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("goal_status", sa.String(length=32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("tasks_total", sa.Integer(), nullable=False),
        sa.Column("tasks_succeeded", sa.Integer(), nullable=False),
        sa.Column("tasks_failed", sa.Integer(), nullable=False),
        sa.Column("tool_calls", sa.Integer(), nullable=False),
        sa.Column("retries", sa.Integer(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_agent_metric_agent_id_agent"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_metric")),
    )
    op.create_index(
        op.f("ix_agent_metric_agent_id"), "agent_metric", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_agent_metric_agent_slug"), "agent_metric", ["agent_slug"], unique=False
    )
    op.create_index(
        op.f("ix_agent_metric_deleted_at"), "agent_metric", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_agent_metric_organization_id"),
        "agent_metric",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_metric_run_id"), "agent_metric", ["run_id"], unique=False
    )

    op.create_table(
        "agent_reflection",
        sa.Column("run_id", app.models.types.GUID(), nullable=False),
        sa.Column("agent_id", app.models.types.GUID(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("mistakes", sa.JSON(), nullable=False),
        sa.Column("lessons", sa.JSON(), nullable=False),
        sa.Column("improvements", sa.JSON(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_agent_reflection_agent_id_agent"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_reflection")),
    )
    op.create_index(
        op.f("ix_agent_reflection_agent_id"),
        "agent_reflection",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_reflection_deleted_at"),
        "agent_reflection",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_reflection_run_id"), "agent_reflection", ["run_id"], unique=False
    )

    op.create_table(
        "agent_version",
        sa.Column("agent_id", app.models.types.GUID(), nullable=False),
        sa.Column("version_label", sa.String(length=32), nullable=False),
        sa.Column("changelog", sa.Text(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_agent_version_agent_id_agent"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_version")),
        sa.UniqueConstraint("agent_id", "version_label", name="uq_agent_version"),
    )
    op.create_index(
        op.f("ix_agent_version_agent_id"), "agent_version", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_agent_version_deleted_at"), "agent_version", ["deleted_at"], unique=False
    )

    op.create_table(
        "agent_workflow_run",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("agent_id", app.models.types.GUID(), nullable=True),
        sa.Column("run_id", app.models.types.GUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_agent_workflow_run_agent_id_agent"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_workflow_run")),
    )
    op.create_index(
        op.f("ix_agent_workflow_run_agent_id"),
        "agent_workflow_run",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_workflow_run_deleted_at"),
        "agent_workflow_run",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_workflow_run_organization_id"),
        "agent_workflow_run",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_workflow_run_run_id"),
        "agent_workflow_run",
        ["run_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_document",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("agent_id", app.models.types.GUID(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=512), nullable=True),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_knowledge_document_agent_id_agent"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_knowledge_document_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_document")),
    )
    op.create_index(
        op.f("ix_knowledge_document_agent_id"),
        "knowledge_document",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_document_deleted_at"),
        "knowledge_document",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_document_organization_id"),
        "knowledge_document",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "agent_plan",
        sa.Column("goal_id", app.models.types.GUID(), nullable=True),
        sa.Column("run_id", app.models.types.GUID(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("outline", sa.JSON(), nullable=False),
        sa.Column("task_count", sa.Integer(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["agent_goal.id"],
            name=op.f("fk_agent_plan_goal_id_agent_goal"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_plan")),
    )
    op.create_index(
        op.f("ix_agent_plan_deleted_at"), "agent_plan", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_agent_plan_goal_id"), "agent_plan", ["goal_id"], unique=False
    )
    op.create_index(op.f("ix_agent_plan_run_id"), "agent_plan", ["run_id"], unique=False)

    op.create_table(
        "agent_task",
        sa.Column("goal_id", app.models.types.GUID(), nullable=True),
        sa.Column("run_id", app.models.types.GUID(), nullable=True),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("depends_on", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("artifacts", sa.JSON(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["goal_id"],
            ["agent_goal.id"],
            name=op.f("fk_agent_task_goal_id_agent_goal"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_task")),
    )
    op.create_index(
        op.f("ix_agent_task_deleted_at"), "agent_task", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_agent_task_goal_id"), "agent_task", ["goal_id"], unique=False
    )
    op.create_index(op.f("ix_agent_task_run_id"), "agent_task", ["run_id"], unique=False)
    op.create_index(op.f("ix_agent_task_status"), "agent_task", ["status"], unique=False)

    op.create_table(
        "agent_task_execution",
        sa.Column("task_id", app.models.types.GUID(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("output", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("id", app.models.types.GUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", app.models.types.GUID(), nullable=True),
        sa.Column("updated_by", app.models.types.GUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["agent_task.id"],
            name=op.f("fk_agent_task_execution_task_id_agent_task"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_task_execution")),
    )
    op.create_index(
        op.f("ix_agent_task_execution_deleted_at"),
        "agent_task_execution",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_agent_task_execution_task_id"),
        "agent_task_execution",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the tables introduced by this revision.

    Reverse creation order, so a table is gone before whatever it references.
    Indexes belong to their table and go with it.
    """
    op.drop_table("agent_task_execution")
    op.drop_table("agent_task")
    op.drop_table("agent_plan")
    op.drop_table("knowledge_document")
    op.drop_table("agent_workflow_run")
    op.drop_table("agent_version")
    op.drop_table("agent_reflection")
    op.drop_table("agent_metric")
    op.drop_table("agent_memory")
    op.drop_table("agent_goal")
    op.drop_table("agent_evaluation")
    op.drop_table("agent_configuration")
    op.drop_table("agent")
    op.drop_table("agent_tool_execution")
    op.drop_table("agent_tool")
