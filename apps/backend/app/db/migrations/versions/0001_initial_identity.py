"""Initial identity & access-management schema.

Users, profiles, organizations, teams, roles, permissions, sessions,
tokens, OAuth accounts, API keys, invitations, and audit logs.

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

Revision ID: 0001_identity
Revises:
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import app.models.types
import sqlalchemy as sa
from alembic import op

revision: str = "0001_identity"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the tables introduced by this revision."""
    op.create_table(
        "permission",
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permission")),
    )
    op.create_index(
        op.f("ix_permission_deleted_at"), "permission", ["deleted_at"], unique=False
    )
    op.create_index(op.f("ix_permission_slug"), "permission", ["slug"], unique=True)

    op.create_table(
        "user",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user")),
    )
    op.create_index(op.f("ix_user_deleted_at"), "user", ["deleted_at"], unique=False)
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)
    op.create_index(op.f("ix_user_username"), "user", ["username"], unique=True)

    op.create_table(
        "email_verification_token",
        sa.Column("user_id", app.models.types.GUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_email_verification_token_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_verification_token")),
    )
    op.create_index(
        op.f("ix_email_verification_token_deleted_at"),
        "email_verification_token",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_verification_token_token_hash"),
        "email_verification_token",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_email_verification_token_user_id"),
        "email_verification_token",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "o_auth_account",
        sa.Column("user_id", app.models.types.GUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("access_token", sa.String(length=2048), nullable=True),
        sa.Column("refresh_token", sa.String(length=2048), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_o_auth_account_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_o_auth_account")),
        sa.UniqueConstraint(
            "provider", "provider_account_id", name="uq_oauth_provider_account"
        ),
    )
    op.create_index(
        op.f("ix_o_auth_account_deleted_at"),
        "o_auth_account",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_o_auth_account_provider"), "o_auth_account", ["provider"], unique=False
    )
    op.create_index(
        op.f("ix_o_auth_account_user_id"), "o_auth_account", ["user_id"], unique=False
    )

    op.create_table(
        "organization",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("owner_id", app.models.types.GUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["user.id"],
            name=op.f("fk_organization_owner_id_user"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization")),
    )
    op.create_index(
        op.f("ix_organization_deleted_at"), "organization", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_organization_owner_id"), "organization", ["owner_id"], unique=False
    )
    op.create_index(op.f("ix_organization_slug"), "organization", ["slug"], unique=True)

    op.create_table(
        "password_reset_token",
        sa.Column("user_id", app.models.types.GUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_password_reset_token_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_token")),
    )
    op.create_index(
        op.f("ix_password_reset_token_deleted_at"),
        "password_reset_token",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_password_reset_token_token_hash"),
        "password_reset_token",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_password_reset_token_user_id"),
        "password_reset_token",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "profile",
        sa.Column("user_id", app.models.types.GUID(), nullable=False),
        sa.Column("bio", sa.String(length=2048), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("website", sa.String(length=1024), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_profile_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profile")),
        sa.UniqueConstraint("user_id", name=op.f("uq_profile_user_id")),
    )
    op.create_index(
        op.f("ix_profile_deleted_at"), "profile", ["deleted_at"], unique=False
    )

    op.create_table(
        "session",
        sa.Column("user_id", app.models.types.GUID(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("browser", sa.String(length=128), nullable=True),
        sa.Column("os", sa.String(length=128), nullable=True),
        sa.Column("device", sa.String(length=128), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("last_activity", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_session_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_session")),
    )
    op.create_index(
        op.f("ix_session_deleted_at"), "session", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_session_revoked_at"), "session", ["revoked_at"], unique=False
    )
    op.create_index(op.f("ix_session_user_id"), "session", ["user_id"], unique=False)

    op.create_table(
        "api_key",
        sa.Column("user_id", app.models.types.GUID(), nullable=False),
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_api_key_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_api_key_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_key")),
    )
    op.create_index(
        op.f("ix_api_key_deleted_at"), "api_key", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_api_key_organization_id"), "api_key", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_api_key_prefix"), "api_key", ["prefix"], unique=True)
    op.create_index(
        op.f("ix_api_key_revoked_at"), "api_key", ["revoked_at"], unique=False
    )
    op.create_index(op.f("ix_api_key_user_id"), "api_key", ["user_id"], unique=False)

    op.create_table(
        "audit_log",
        sa.Column("actor_id", app.models.types.GUID(), nullable=True),
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
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
            name=op.f("fk_audit_log_actor_id_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_audit_log_organization_id_organization"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_action"), "audit_log", ["action"], unique=False)
    op.create_index(
        op.f("ix_audit_log_actor_id"), "audit_log", ["actor_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_log_organization_id"),
        "audit_log",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "refresh_token",
        sa.Column("user_id", app.models.types.GUID(), nullable=False),
        sa.Column("session_id", app.models.types.GUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_to", app.models.types.GUID(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["session.id"],
            name=op.f("fk_refresh_token_session_id_session"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_refresh_token_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_token")),
    )
    op.create_index(
        op.f("ix_refresh_token_deleted_at"), "refresh_token", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_refresh_token_expires_at"), "refresh_token", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_refresh_token_session_id"), "refresh_token", ["session_id"], unique=False
    )
    op.create_index(
        op.f("ix_refresh_token_token_hash"), "refresh_token", ["token_hash"], unique=True
    )
    op.create_index(
        op.f("ix_refresh_token_user_id"), "refresh_token", ["user_id"], unique=False
    )

    op.create_table(
        "role",
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_role_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role")),
        sa.UniqueConstraint("organization_id", "slug", name="uq_role_org_slug"),
    )
    op.create_index(op.f("ix_role_deleted_at"), "role", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_role_organization_id"), "role", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_role_slug"), "role", ["slug"], unique=False)

    op.create_table(
        "team",
        sa.Column("organization_id", app.models.types.GUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_team_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team")),
        sa.UniqueConstraint("organization_id", "slug", name="uq_team_org_slug"),
    )
    op.create_index(op.f("ix_team_deleted_at"), "team", ["deleted_at"], unique=False)
    op.create_index(
        op.f("ix_team_organization_id"), "team", ["organization_id"], unique=False
    )

    op.create_table(
        "invitation",
        sa.Column("organization_id", app.models.types.GUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role_id", app.models.types.GUID(), nullable=False),
        sa.Column("invited_by_id", app.models.types.GUID(), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["invited_by_id"],
            ["user.id"],
            name=op.f("fk_invitation_invited_by_id_user"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_invitation_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role.id"],
            name=op.f("fk_invitation_role_id_role"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invitation")),
    )
    op.create_index(
        op.f("ix_invitation_deleted_at"), "invitation", ["deleted_at"], unique=False
    )
    op.create_index(op.f("ix_invitation_email"), "invitation", ["email"], unique=False)
    op.create_index(
        op.f("ix_invitation_organization_id"),
        "invitation",
        ["organization_id"],
        unique=False,
    )
    op.create_index(op.f("ix_invitation_status"), "invitation", ["status"], unique=False)
    op.create_index(
        op.f("ix_invitation_token_hash"), "invitation", ["token_hash"], unique=True
    )

    op.create_table(
        "organization_member",
        sa.Column("organization_id", app.models.types.GUID(), nullable=False),
        sa.Column("user_id", app.models.types.GUID(), nullable=False),
        sa.Column("role_id", app.models.types.GUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_organization_member_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role.id"],
            name=op.f("fk_organization_member_role_id_role"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_organization_member_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_member")),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member_org_user"),
    )
    op.create_index(
        op.f("ix_organization_member_deleted_at"),
        "organization_member",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_member_organization_id"),
        "organization_member",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_member_user_id"),
        "organization_member",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "role_permission",
        sa.Column("role_id", app.models.types.GUID(), nullable=False),
        sa.Column("permission_id", app.models.types.GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permission.id"],
            name=op.f("fk_role_permission_permission_id_permission"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role.id"],
            name=op.f("fk_role_permission_role_id_role"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "role_id", "permission_id", name=op.f("pk_role_permission")
        ),
    )

    op.create_table(
        "team_member",
        sa.Column("team_id", app.models.types.GUID(), nullable=False),
        sa.Column("user_id", app.models.types.GUID(), nullable=False),
        sa.Column("role_id", app.models.types.GUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["role.id"],
            name=op.f("fk_team_member_role_id_role"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["team_id"],
            ["team.id"],
            name=op.f("fk_team_member_team_id_team"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_team_member_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_team_member")),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_member_team_user"),
    )
    op.create_index(
        op.f("ix_team_member_deleted_at"), "team_member", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_team_member_team_id"), "team_member", ["team_id"], unique=False
    )
    op.create_index(
        op.f("ix_team_member_user_id"), "team_member", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Drop the tables introduced by this revision.

    Reverse creation order, so a table is gone before whatever it references.
    Indexes belong to their table and go with it.
    """
    op.drop_table("team_member")
    op.drop_table("role_permission")
    op.drop_table("organization_member")
    op.drop_table("invitation")
    op.drop_table("team")
    op.drop_table("role")
    op.drop_table("refresh_token")
    op.drop_table("audit_log")
    op.drop_table("api_key")
    op.drop_table("session")
    op.drop_table("profile")
    op.drop_table("password_reset_token")
    op.drop_table("organization")
    op.drop_table("o_auth_account")
    op.drop_table("email_verification_token")
    op.drop_table("user")
    op.drop_table("permission")
