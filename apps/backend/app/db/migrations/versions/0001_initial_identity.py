"""Initial identity & access-management schema.

Creates the full Phase 02 schema (users, profiles, organizations, teams, roles,
permissions, sessions, tokens, OAuth accounts, API keys, invitations, audit
logs). This baseline migration builds every table from the ORM metadata so the
schema stays authoritative in the models and portable across dialects (the
``GUID`` type maps to PostgreSQL ``UUID`` and ``CHAR(36)`` elsewhere). Subsequent
migrations use ``--autogenerate`` for incremental changes.

Revision ID: 0001_identity
Revises:
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from app.models import Base

revision: str = "0001_identity"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all identity tables from the ORM metadata."""
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop all identity tables."""
    Base.metadata.drop_all(bind=op.get_bind())
