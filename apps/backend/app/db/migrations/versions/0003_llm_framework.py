"""LLM framework schema.

Prompts and versions, conversations and messages, token and cost
accounting, provider and model configuration.

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

Revision ID: 0003_llm
Revises: 0002_core_infra
Create Date: 2026-07-27
"""

from __future__ import annotations

from collections.abc import Sequence

import app.models.types
import sqlalchemy as sa
from alembic import op

revision: str = "0003_llm"
down_revision: str | None = "0002_core_infra"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the tables introduced by this revision."""
    op.create_table(
        "llm_cost_rollup",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("cost_date", sa.Date(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("input_cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("output_cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("total_cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_cost_rollup")),
        sa.UniqueConstraint(
            "organization_id", "cost_date", "model", name="uq_cost_org_date_model"
        ),
    )
    op.create_index(
        op.f("ix_llm_cost_rollup_cost_date"),
        "llm_cost_rollup",
        ["cost_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_cost_rollup_organization_id"),
        "llm_cost_rollup",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "llm_usage_rollup",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("user_id", app.models.types.GUID(), nullable=True),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_usage_rollup")),
        sa.UniqueConstraint(
            "organization_id", "usage_date", "model", name="uq_usage_org_date_model"
        ),
    )
    op.create_index(
        op.f("ix_llm_usage_rollup_organization_id"),
        "llm_usage_rollup",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_usage_rollup_usage_date"),
        "llm_usage_rollup",
        ["usage_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_usage_rollup_user_id"), "llm_usage_rollup", ["user_id"], unique=False
    )

    op.create_table(
        "model_configuration",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("streaming", sa.Boolean(), nullable=False),
        sa.Column("timeout_seconds", sa.Float(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_configuration")),
        sa.UniqueConstraint("organization_id", "model", name="uq_model_config_org_model"),
    )
    op.create_index(
        op.f("ix_model_configuration_deleted_at"),
        "model_configuration",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_model_configuration_organization_id"),
        "model_configuration",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "provider_configuration",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provider_configuration")),
        sa.UniqueConstraint("organization_id", "provider", name="uq_provider_org_slug"),
    )
    op.create_index(
        op.f("ix_provider_configuration_deleted_at"),
        "provider_configuration",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_provider_configuration_organization_id"),
        "provider_configuration",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "tool_execution",
        sa.Column("request_id", app.models.types.GUID(), nullable=True),
        sa.Column("conversation_id", app.models.types.GUID(), nullable=True),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("is_error", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_execution")),
    )
    op.create_index(
        op.f("ix_tool_execution_conversation_id"),
        "tool_execution",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tool_execution_deleted_at"),
        "tool_execution",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tool_execution_request_id"),
        "tool_execution",
        ["request_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tool_execution_tool_name"), "tool_execution", ["tool_name"], unique=False
    )

    op.create_table(
        "conversation",
        sa.Column("organization_id", app.models.types.GUID(), nullable=False),
        sa.Column("user_id", app.models.types.GUID(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("system", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
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
            name=op.f("fk_conversation_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_conversation_user_id_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation")),
    )
    op.create_index(
        op.f("ix_conversation_deleted_at"), "conversation", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_conversation_organization_id"),
        "conversation",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_user_id"), "conversation", ["user_id"], unique=False
    )

    op.create_table(
        "llm_request",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("user_id", app.models.types.GUID(), nullable=True),
        sa.Column("project_id", app.models.types.GUID(), nullable=True),
        sa.Column("agent_id", app.models.types.GUID(), nullable=True),
        sa.Column("conversation_id", app.models.types.GUID(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("streamed", sa.Boolean(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
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
            name=op.f("fk_llm_request_organization_id_organization"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_llm_request_user_id_user"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_request")),
    )
    op.create_index(
        op.f("ix_llm_request_agent_id"), "llm_request", ["agent_id"], unique=False
    )
    op.create_index(
        op.f("ix_llm_request_conversation_id"),
        "llm_request",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_request_correlation_id"),
        "llm_request",
        ["correlation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_request_deleted_at"), "llm_request", ["deleted_at"], unique=False
    )
    op.create_index(op.f("ix_llm_request_model"), "llm_request", ["model"], unique=False)
    op.create_index(
        op.f("ix_llm_request_organization_id"),
        "llm_request",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_request_project_id"), "llm_request", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_llm_request_status"), "llm_request", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_llm_request_user_id"), "llm_request", ["user_id"], unique=False
    )

    op.create_table(
        "prompt_template",
        sa.Column("organization_id", app.models.types.GUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latest_version", sa.Integer(), nullable=False),
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
            name=op.f("fk_prompt_template_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_template")),
        sa.UniqueConstraint("organization_id", "name", name="uq_prompt_org_name"),
    )
    op.create_index(
        op.f("ix_prompt_template_category"), "prompt_template", ["category"], unique=False
    )
    op.create_index(
        op.f("ix_prompt_template_deleted_at"),
        "prompt_template",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prompt_template_organization_id"),
        "prompt_template",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prompt_template_status"), "prompt_template", ["status"], unique=False
    )

    op.create_table(
        "conversation_message",
        sa.Column("conversation_id", app.models.types.GUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=False),
        sa.Column("tokens", sa.Integer(), nullable=False),
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
            ["conversation_id"],
            ["conversation.id"],
            name=op.f("fk_conversation_message_conversation_id_conversation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_message")),
    )
    op.create_index(
        op.f("ix_conversation_message_conversation_id"),
        "conversation_message",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_message_deleted_at"),
        "conversation_message",
        ["deleted_at"],
        unique=False,
    )

    op.create_table(
        "conversation_summary",
        sa.Column("conversation_id", app.models.types.GUID(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
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
            ["conversation_id"],
            ["conversation.id"],
            name=op.f("fk_conversation_summary_conversation_id_conversation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_summary")),
    )
    op.create_index(
        op.f("ix_conversation_summary_conversation_id"),
        "conversation_summary",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_summary_deleted_at"),
        "conversation_summary",
        ["deleted_at"],
        unique=False,
    )

    op.create_table(
        "prompt_version",
        sa.Column("template_id", app.models.types.GUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("variables", sa.JSON(), nullable=False),
        sa.Column("examples", sa.JSON(), nullable=False),
        sa.Column("performance_score", sa.Float(), nullable=True),
        sa.Column("token_usage", sa.Integer(), nullable=False),
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
            ["template_id"],
            ["prompt_template.id"],
            name=op.f("fk_prompt_version_template_id_prompt_template"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_version")),
        sa.UniqueConstraint("template_id", "version_number", name="uq_prompt_version"),
    )
    op.create_index(
        op.f("ix_prompt_version_deleted_at"),
        "prompt_version",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_prompt_version_template_id"),
        "prompt_version",
        ["template_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the tables introduced by this revision.

    Reverse creation order, so a table is gone before whatever it references.
    Indexes belong to their table and go with it.
    """
    op.drop_table("prompt_version")
    op.drop_table("conversation_summary")
    op.drop_table("conversation_message")
    op.drop_table("prompt_template")
    op.drop_table("llm_request")
    op.drop_table("conversation")
    op.drop_table("tool_execution")
    op.drop_table("provider_configuration")
    op.drop_table("model_configuration")
    op.drop_table("llm_usage_rollup")
    op.drop_table("llm_cost_rollup")
