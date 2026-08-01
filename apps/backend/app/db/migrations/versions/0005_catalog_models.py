"""Billing, notification, and job catalog tables.

Adds the remaining Phase 06 breadth: plans/subscriptions/invoices/payments,
metered usage and internal cost records, notifications/preferences and outbound
webhooks with their delivery attempts, and the durable queue/render job records.
Built from ORM metadata (portable across dialects); prior tables are untouched.

Revision ID: 0005_catalog
Revises: 0004_agent
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.models import Base

revision: str = "0005_catalog"
down_revision: str | None = "0004_agent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TABLES = (
    "plan",
    "subscription",
    "invoice",
    "payment",
    "usage_record",
    "cost_record",
    "notification",
    "notification_preference",
    "webhook",
    "webhook_delivery",
    "queue_job",
    "render_job",
)


def upgrade() -> None:
    """Create the catalog tables."""
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _NEW_TABLES]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    """Drop the tables introduced in this migration."""
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in reversed(_NEW_TABLES)]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)
