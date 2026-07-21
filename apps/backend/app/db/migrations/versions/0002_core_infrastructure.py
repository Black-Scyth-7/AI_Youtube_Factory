"""Core infrastructure & content domain schema.

Adds the Phase 03 tables — workspaces, projects, channels, videos (+ versions),
folders, media files, tags (+ video_tag), workflows (+ nodes, edges,
executions), feature flags, and the activity log. Builds the new tables from the
ORM metadata (portable across dialects); existing Phase 02 tables are untouched.

Revision ID: 0002_core_infra
Revises: 0001_identity
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.models import Base

revision: str = "0002_core_infra"
down_revision: str | None = "0001_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables introduced in this migration (in dependency order).
_NEW_TABLES = (
    "workspace",
    "project",
    "channel",
    "video",
    "video_version",
    "folder",
    "media_file",
    "tag",
    "video_tag",
    "workflow",
    "workflow_node",
    "workflow_edge",
    "workflow_execution",
    "feature_flag",
    "activity_log",
)


def upgrade() -> None:
    """Create the new domain and infrastructure tables."""
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _NEW_TABLES]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    """Drop the tables introduced in this migration."""
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in reversed(_NEW_TABLES)]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)
