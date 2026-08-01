"""Core infrastructure schema.

Domain models, activity logs, stored media, workflow definitions,
projects and folders, and feature flags.

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

Revision ID: 0002_core_infra
Revises: 0001_identity
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

import app.models.types
import sqlalchemy as sa
from alembic import op

revision: str = "0002_core_infra"
down_revision: str | None = "0001_identity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the tables introduced by this revision."""
    op.create_table(
        "feature_flag",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("rollout_percentage", sa.Integer(), nullable=False),
        sa.Column("targets", sa.JSON(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feature_flag")),
    )
    op.create_index(
        op.f("ix_feature_flag_deleted_at"), "feature_flag", ["deleted_at"], unique=False
    )
    op.create_index(op.f("ix_feature_flag_key"), "feature_flag", ["key"], unique=True)

    op.create_table(
        "activity_log",
        sa.Column("actor_id", app.models.types.GUID(), nullable=True),
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["user.id"],
            name=op.f("fk_activity_log_actor_id_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_activity_log_organization_id_organization"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_log")),
    )
    op.create_index(
        op.f("ix_activity_log_action"), "activity_log", ["action"], unique=False
    )
    op.create_index(
        op.f("ix_activity_log_actor_id"), "activity_log", ["actor_id"], unique=False
    )
    op.create_index(
        op.f("ix_activity_log_organization_id"),
        "activity_log",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "tag",
        sa.Column("organization_id", app.models.types.GUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
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
            name=op.f("fk_tag_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tag")),
        sa.UniqueConstraint("organization_id", "slug", name="uq_tag_org_slug"),
    )
    op.create_index(op.f("ix_tag_deleted_at"), "tag", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_tag_organization_id"), "tag", ["organization_id"], unique=False
    )

    op.create_table(
        "workspace",
        sa.Column("organization_id", app.models.types.GUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
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
            name=op.f("fk_workspace_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace")),
        sa.UniqueConstraint("organization_id", "slug", name="uq_workspace_org_slug"),
    )
    op.create_index(
        op.f("ix_workspace_deleted_at"), "workspace", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_workspace_organization_id"),
        "workspace",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "folder",
        sa.Column("workspace_id", app.models.types.GUID(), nullable=False),
        sa.Column("parent_id", app.models.types.GUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
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
            ["parent_id"],
            ["folder.id"],
            name=op.f("fk_folder_parent_id_folder"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspace.id"],
            name=op.f("fk_folder_workspace_id_workspace"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_folder")),
    )
    op.create_index(op.f("ix_folder_deleted_at"), "folder", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_folder_parent_id"), "folder", ["parent_id"], unique=False)
    op.create_index(
        op.f("ix_folder_workspace_id"), "folder", ["workspace_id"], unique=False
    )

    op.create_table(
        "project",
        sa.Column("workspace_id", app.models.types.GUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
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
            ["workspace_id"],
            ["workspace.id"],
            name=op.f("fk_project_workspace_id_workspace"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project")),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_project_ws_slug"),
    )
    op.create_index(
        op.f("ix_project_deleted_at"), "project", ["deleted_at"], unique=False
    )
    op.create_index(op.f("ix_project_status"), "project", ["status"], unique=False)
    op.create_index(
        op.f("ix_project_workspace_id"), "project", ["workspace_id"], unique=False
    )

    op.create_table(
        "workflow",
        sa.Column("workspace_id", app.models.types.GUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
            ["workspace_id"],
            ["workspace.id"],
            name=op.f("fk_workflow_workspace_id_workspace"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow")),
    )
    op.create_index(
        op.f("ix_workflow_deleted_at"), "workflow", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_workflow_workspace_id"), "workflow", ["workspace_id"], unique=False
    )

    op.create_table(
        "channel",
        sa.Column("project_id", app.models.types.GUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("youtube_channel_id", sa.String(length=128), nullable=True),
        sa.Column("handle", sa.String(length=128), nullable=True),
        sa.Column("is_connected", sa.Boolean(), nullable=False),
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
            ["project_id"],
            ["project.id"],
            name=op.f("fk_channel_project_id_project"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_channel")),
    )
    op.create_index(
        op.f("ix_channel_deleted_at"), "channel", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_channel_project_id"), "channel", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_channel_youtube_channel_id"),
        "channel",
        ["youtube_channel_id"],
        unique=False,
    )

    op.create_table(
        "media_file",
        sa.Column("workspace_id", app.models.types.GUID(), nullable=False),
        sa.Column("folder_id", app.models.types.GUID(), nullable=True),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
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
            ["folder_id"],
            ["folder.id"],
            name=op.f("fk_media_file_folder_id_folder"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspace.id"],
            name=op.f("fk_media_file_workspace_id_workspace"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_file")),
        sa.UniqueConstraint("workspace_id", "sha256", name="uq_media_ws_sha"),
    )
    op.create_index(
        op.f("ix_media_file_deleted_at"), "media_file", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_media_file_folder_id"), "media_file", ["folder_id"], unique=False
    )
    op.create_index(op.f("ix_media_file_sha256"), "media_file", ["sha256"], unique=False)
    op.create_index(
        op.f("ix_media_file_workspace_id"), "media_file", ["workspace_id"], unique=False
    )

    op.create_table(
        "workflow_edge",
        sa.Column("workflow_id", app.models.types.GUID(), nullable=False),
        sa.Column("source_key", sa.String(length=128), nullable=False),
        sa.Column("target_key", sa.String(length=128), nullable=False),
        sa.Column("condition", sa.String(length=512), nullable=True),
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
            name=op.f("fk_workflow_edge_workflow_id_workflow"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_edge")),
    )
    op.create_index(
        op.f("ix_workflow_edge_deleted_at"), "workflow_edge", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_workflow_edge_workflow_id"),
        "workflow_edge",
        ["workflow_id"],
        unique=False,
    )

    op.create_table(
        "workflow_execution",
        sa.Column("workflow_id", app.models.types.GUID(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("logs", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_workflow_execution_workflow_id_workflow"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_execution")),
    )
    op.create_index(
        op.f("ix_workflow_execution_deleted_at"),
        "workflow_execution",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_execution_status"),
        "workflow_execution",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_execution_workflow_id"),
        "workflow_execution",
        ["workflow_id"],
        unique=False,
    )

    op.create_table(
        "workflow_node",
        sa.Column("workflow_id", app.models.types.GUID(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("position", sa.JSON(), nullable=False),
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
            name=op.f("fk_workflow_node_workflow_id_workflow"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_node")),
        sa.UniqueConstraint("workflow_id", "key", name="uq_workflow_node_key"),
    )
    op.create_index(
        op.f("ix_workflow_node_deleted_at"), "workflow_node", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_workflow_node_workflow_id"),
        "workflow_node",
        ["workflow_id"],
        unique=False,
    )

    op.create_table(
        "video",
        sa.Column("project_id", app.models.types.GUID(), nullable=False),
        sa.Column("channel_id", app.models.types.GUID(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_version_id", app.models.types.GUID(), nullable=True),
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
            ["channel_id"],
            ["channel.id"],
            name=op.f("fk_video_channel_id_channel"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.id"],
            name=op.f("fk_video_project_id_project"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_video")),
    )
    op.create_index(op.f("ix_video_channel_id"), "video", ["channel_id"], unique=False)
    op.create_index(op.f("ix_video_deleted_at"), "video", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_video_project_id"), "video", ["project_id"], unique=False)
    op.create_index(op.f("ix_video_status"), "video", ["status"], unique=False)

    op.create_table(
        "video_tag",
        sa.Column("video_id", app.models.types.GUID(), nullable=False),
        sa.Column("tag_id", app.models.types.GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tag.id"],
            name=op.f("fk_video_tag_tag_id_tag"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["video.id"],
            name=op.f("fk_video_tag_video_id_video"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("video_id", "tag_id", name=op.f("pk_video_tag")),
    )

    op.create_table(
        "video_version",
        sa.Column("video_id", app.models.types.GUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("script", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
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
            name=op.f("fk_video_version_video_id_video"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_video_version")),
        sa.UniqueConstraint("video_id", "version_number", name="uq_video_version_num"),
    )
    op.create_index(
        op.f("ix_video_version_deleted_at"), "video_version", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_video_version_video_id"), "video_version", ["video_id"], unique=False
    )


def downgrade() -> None:
    """Drop the tables introduced by this revision.

    Reverse creation order, so a table is gone before whatever it references.
    Indexes belong to their table and go with it.
    """
    op.drop_table("video_version")
    op.drop_table("video_tag")
    op.drop_table("video")
    op.drop_table("workflow_node")
    op.drop_table("workflow_execution")
    op.drop_table("workflow_edge")
    op.drop_table("media_file")
    op.drop_table("channel")
    op.drop_table("workflow")
    op.drop_table("project")
    op.drop_table("folder")
    op.drop_table("workspace")
    op.drop_table("tag")
    op.drop_table("activity_log")
    op.drop_table("feature_flag")
