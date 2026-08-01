"""Workflow triggers and per-node execution records.

Adds the Phase 07 tables: what starts a workflow (manual/schedule/event) and the
per-node outcome of each run, which is what a visual editor renders. Built from
ORM metadata (portable across dialects); prior tables are untouched.

Revision ID: 0006_workflow
Revises: 0005_catalog
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.models import Base

revision: str = "0006_workflow"
down_revision: str | None = "0005_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TABLES = (
    "workflow_trigger",
    "workflow_node_execution",
)


def upgrade() -> None:
    """Create the workflow engine tables."""
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _NEW_TABLES]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    """Drop the tables introduced in this migration."""
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in reversed(_NEW_TABLES)]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)
