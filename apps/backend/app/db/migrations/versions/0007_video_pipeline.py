"""Video pipeline schema.

Research notes, pipeline runs, publications, daily analytics records,
and the performance lessons that close the learning loop.

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

Revision ID: 0007_pipeline
Revises: 0006_workflow
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

import app.models.types
import sqlalchemy as sa
from alembic import op

revision: str = "0007_pipeline"
down_revision: str | None = "0006_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the tables introduced by this revision."""
    op.create_table(
        "performance_lesson",
        sa.Column("video_id", app.models.types.GUID(), nullable=True),
        sa.Column("channel_id", app.models.types.GUID(), nullable=True),
        sa.Column("dimension", sa.String(length=64), nullable=False),
        sa.Column("observation", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
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
            ["video_id"],
            ["video.id"],
            name=op.f("fk_performance_lesson_video_id_video"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_performance_lesson")),
    )
    op.create_index(
        op.f("ix_performance_lesson_channel_id"),
        "performance_lesson",
        ["channel_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_performance_lesson_deleted_at"),
        "performance_lesson",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_performance_lesson_dimension"),
        "performance_lesson",
        ["dimension"],
        unique=False,
    )
    op.create_index(
        op.f("ix_performance_lesson_video_id"),
        "performance_lesson",
        ["video_id"],
        unique=False,
    )

    op.create_table(
        "pipeline_run",
        sa.Column("video_id", app.models.types.GUID(), nullable=False),
        sa.Column("stage", sa.String(length=24), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
            ["video_id"],
            ["video.id"],
            name=op.f("fk_pipeline_run_video_id_video"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_run")),
    )
    op.create_index(
        op.f("ix_pipeline_run_deleted_at"), "pipeline_run", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_pipeline_run_stage"), "pipeline_run", ["stage"], unique=False
    )
    op.create_index(
        op.f("ix_pipeline_run_video_id"), "pipeline_run", ["video_id"], unique=False
    )

    op.create_table(
        "publication",
        sa.Column("video_id", app.models.types.GUID(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
            ["video_id"],
            ["video.id"],
            name=op.f("fk_publication_video_id_video"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_publication")),
        sa.UniqueConstraint(
            "video_id", "platform", name="uq_publication_video_id_platform"
        ),
    )
    op.create_index(
        op.f("ix_publication_deleted_at"), "publication", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_publication_external_id"), "publication", ["external_id"], unique=False
    )
    op.create_index(
        op.f("ix_publication_platform"), "publication", ["platform"], unique=False
    )
    op.create_index(
        op.f("ix_publication_status"), "publication", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_publication_video_id"), "publication", ["video_id"], unique=False
    )

    op.create_table(
        "research_note",
        sa.Column("video_id", app.models.types.GUID(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("relevance", sa.Float(), nullable=False),
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
            ["video_id"],
            ["video.id"],
            name=op.f("fk_research_note_video_id_video"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_note")),
    )
    op.create_index(
        op.f("ix_research_note_deleted_at"), "research_note", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_research_note_video_id"), "research_note", ["video_id"], unique=False
    )

    op.create_table(
        "analytics_record",
        sa.Column("publication_id", app.models.types.GUID(), nullable=False),
        sa.Column("measured_on", sa.Date(), nullable=False),
        sa.Column("views", sa.BigInteger(), nullable=False),
        sa.Column("likes", sa.Integer(), nullable=False),
        sa.Column("comments", sa.Integer(), nullable=False),
        sa.Column("watch_time_seconds", sa.BigInteger(), nullable=False),
        sa.Column("impressions", sa.BigInteger(), nullable=False),
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
            ["publication_id"],
            ["publication.id"],
            name=op.f("fk_analytics_record_publication_id_publication"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analytics_record")),
        sa.UniqueConstraint(
            "publication_id",
            "measured_on",
            name="uq_analytics_publication_id_measured_on",
        ),
    )
    op.create_index(
        op.f("ix_analytics_record_deleted_at"),
        "analytics_record",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_record_measured_on"),
        "analytics_record",
        ["measured_on"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_record_publication_id"),
        "analytics_record",
        ["publication_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the tables introduced by this revision.

    Reverse creation order, so a table is gone before whatever it references.
    Indexes belong to their table and go with it.
    """
    op.drop_table("analytics_record")
    op.drop_table("research_note")
    op.drop_table("publication")
    op.drop_table("pipeline_run")
    op.drop_table("performance_lesson")
