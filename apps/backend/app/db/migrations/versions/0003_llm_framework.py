"""LLM framework schema.

Adds the Phase 04 tables — prompt templates/versions, conversations/messages/
summaries, per-request accounting (llm_request), usage/cost rollups, tool
executions, and model/provider configuration. Built from ORM metadata (portable
across dialects); prior tables are untouched.

Revision ID: 0003_llm
Revises: 0002_core_infra
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.models import Base

revision: str = "0003_llm"
down_revision: str | None = "0002_core_infra"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TABLES = (
    "prompt_template",
    "prompt_version",
    "conversation",
    "conversation_message",
    "conversation_summary",
    "llm_request",
    "llm_usage_rollup",
    "llm_cost_rollup",
    "tool_execution",
    "model_configuration",
    "provider_configuration",
)


def upgrade() -> None:
    """Create the LLM framework tables."""
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _NEW_TABLES]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    """Drop the LLM framework tables."""
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in reversed(_NEW_TABLES)]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)
