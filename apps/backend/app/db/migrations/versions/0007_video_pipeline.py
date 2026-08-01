"""Video pipeline schema.

Adds the Phase 08 tables: research notes, pipeline runs, publications, daily
analytics records, and the performance lessons that close the learning loop.
Built from ORM metadata (portable across dialects); prior tables are untouched.

Revision ID: 0007_pipeline
Revises: 0006_workflow
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.models import Base

revision: str = "0007_pipeline"
down_revision: str | None = "0006_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TABLES = (
    "research_note",
    "pipeline_run",
    "publication",
    "analytics_record",
    "performance_lesson",
)


def upgrade() -> None:
    """Create the video pipeline tables."""
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _NEW_TABLES]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    """Drop the tables introduced in this migration."""
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in reversed(_NEW_TABLES)]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)
