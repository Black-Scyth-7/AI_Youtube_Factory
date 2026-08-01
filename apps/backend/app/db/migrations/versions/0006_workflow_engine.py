"""Workflow engine schema.

Workflow triggers and per-node execution records for the Phase 07
engine.

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

Revision ID: 0006_workflow
Revises: 0005_catalog
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

import app.models.types
import sqlalchemy as sa
from alembic import op

revision: str = "0006_workflow"
down_revision: str | None = "0005_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the tables introduced by this revision."""
    op.create_table(
        "workflow_trigger",
        sa.Column("workflow_id", app.models.types.GUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("cron", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=128), nullable=True),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
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
            ["workflow_id"],
            ["workflow.id"],
            name=op.f("fk_workflow_trigger_workflow_id_workflow"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_trigger")),
    )
    op.create_index(
        op.f("ix_workflow_trigger_deleted_at"),
        "workflow_trigger",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_trigger_event_type"),
        "workflow_trigger",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_trigger_is_active"),
        "workflow_trigger",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_trigger_kind"), "workflow_trigger", ["kind"], unique=False
    )
    op.create_index(
        op.f("ix_workflow_trigger_workflow_id"),
        "workflow_trigger",
        ["workflow_id"],
        unique=False,
    )

    op.create_table(
        "workflow_node_execution",
        sa.Column("execution_id", app.models.types.GUID(), nullable=False),
        sa.Column("node_key", sa.String(length=128), nullable=False),
        sa.Column("node_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("skip_reason", sa.String(length=512), nullable=True),
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
            ["execution_id"],
            ["workflow_execution.id"],
            name=op.f("fk_workflow_node_execution_execution_id_workflow_execution"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_node_execution")),
    )
    op.create_index(
        op.f("ix_workflow_node_execution_deleted_at"),
        "workflow_node_execution",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_node_execution_execution_id"),
        "workflow_node_execution",
        ["execution_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_node_execution_node_key"),
        "workflow_node_execution",
        ["node_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_node_execution_status"),
        "workflow_node_execution",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the tables introduced by this revision.

    Reverse creation order, so a table is gone before whatever it references.
    Indexes belong to their table and go with it.
    """
    op.drop_table("workflow_node_execution")
    op.drop_table("workflow_trigger")
