"""AI agent framework schema.

Adds the Phase 05 tables — agents and versions/configurations, goals, tasks and
task executions, agent memory, knowledge documents, tool definitions and
executions, reflections, evaluations, plans, workflow runs, and per-run metrics.
Built from ORM metadata (portable across dialects); prior tables are untouched.

Revision ID: 0004_agent
Revises: 0003_llm
Create Date: 2026-07-22
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.models import Base

revision: str = "0004_agent"
down_revision: str | None = "0003_llm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TABLES = (
    "agent",
    "agent_version",
    "agent_configuration",
    "agent_goal",
    "agent_task",
    "agent_task_execution",
    "agent_memory",
    "knowledge_document",
    "agent_tool",
    "agent_tool_execution",
    "agent_reflection",
    "agent_evaluation",
    "agent_plan",
    "agent_workflow_run",
    "agent_metric",
)


def upgrade() -> None:
    """Create the agent framework tables."""
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _NEW_TABLES]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    """Drop the agent framework tables."""
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in reversed(_NEW_TABLES)]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)
