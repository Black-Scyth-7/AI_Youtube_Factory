"""Billing, notification, and job schema.

Plans, subscriptions, invoices, payments, usage records, notifications
and preferences, webhooks, and the job queue.

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

Revision ID: 0005_catalog
Revises: 0004_agent
Create Date: 2026-08-01
"""

from __future__ import annotations

from collections.abc import Sequence

import app.models.types
import sqlalchemy as sa
from alembic import op

revision: str = "0005_catalog"
down_revision: str | None = "0004_agent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the tables introduced by this revision."""
    op.create_table(
        "plan",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("trial_days", sa.Integer(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("quotas", sa.JSON(), nullable=False),
        sa.Column("overage_rates", sa.JSON(), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan")),
    )
    op.create_index(op.f("ix_plan_code"), "plan", ["code"], unique=True)
    op.create_index(op.f("ix_plan_deleted_at"), "plan", ["deleted_at"], unique=False)

    op.create_table(
        "notification_preference",
        sa.Column("user_id", app.models.types.GUID(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
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
            ["user_id"],
            ["user.id"],
            name=op.f("fk_notification_preference_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_preference")),
    )
    op.create_index(
        op.f("ix_notification_preference_deleted_at"),
        "notification_preference",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_preference_user_id"),
        "notification_preference",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "cost_record",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("vendor", sa.String(length=64), nullable=True),
        sa.Column("amount_usd", sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column("incurred_on", sa.Date(), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_id", app.models.types.GUID(), nullable=True),
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
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_cost_record_organization_id_organization"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cost_record")),
    )
    op.create_index(
        op.f("ix_cost_record_category"), "cost_record", ["category"], unique=False
    )
    op.create_index(
        op.f("ix_cost_record_deleted_at"), "cost_record", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_cost_record_incurred_on"), "cost_record", ["incurred_on"], unique=False
    )
    op.create_index(
        op.f("ix_cost_record_organization_id"),
        "cost_record",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "notification",
        sa.Column("user_id", app.models.types.GUID(), nullable=False),
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("action_url", sa.String(length=1024), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
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
            name=op.f("fk_notification_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name=op.f("fk_notification_user_id_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification")),
    )
    op.create_index(
        op.f("ix_notification_category"), "notification", ["category"], unique=False
    )
    op.create_index(
        op.f("ix_notification_deleted_at"), "notification", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_notification_organization_id"),
        "notification",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_status"), "notification", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_notification_user_id"), "notification", ["user_id"], unique=False
    )

    op.create_table(
        "queue_job",
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("queue", sa.String(length=64), nullable=False),
        sa.Column("task_name", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
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
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_queue_job_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_queue_job")),
        sa.UniqueConstraint("external_id", name=op.f("uq_queue_job_external_id")),
    )
    op.create_index(
        op.f("ix_queue_job_deleted_at"), "queue_job", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_queue_job_organization_id"),
        "queue_job",
        ["organization_id"],
        unique=False,
    )
    op.create_index(op.f("ix_queue_job_queue"), "queue_job", ["queue"], unique=False)
    op.create_index(
        op.f("ix_queue_job_scheduled_for"), "queue_job", ["scheduled_for"], unique=False
    )
    op.create_index(op.f("ix_queue_job_status"), "queue_job", ["status"], unique=False)
    op.create_index(
        op.f("ix_queue_job_task_name"), "queue_job", ["task_name"], unique=False
    )

    op.create_table(
        "subscription",
        sa.Column("organization_id", app.models.types.GUID(), nullable=False),
        sa.Column("plan_id", app.models.types.GUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False),
        sa.Column("external_reference", sa.String(length=128), nullable=True),
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
            name=op.f("fk_subscription_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plan.id"],
            name=op.f("fk_subscription_plan_id_plan"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription")),
        sa.UniqueConstraint(
            "organization_id", "status", name="uq_subscription_organization_id_status"
        ),
    )
    op.create_index(
        op.f("ix_subscription_deleted_at"), "subscription", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_subscription_organization_id"),
        "subscription",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subscription_plan_id"), "subscription", ["plan_id"], unique=False
    )
    op.create_index(
        op.f("ix_subscription_status"), "subscription", ["status"], unique=False
    )

    op.create_table(
        "webhook",
        sa.Column("organization_id", app.models.types.GUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("secret_hash", sa.String(length=128), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
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
            name=op.f("fk_webhook_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook")),
    )
    op.create_index(
        op.f("ix_webhook_deleted_at"), "webhook", ["deleted_at"], unique=False
    )
    op.create_index(op.f("ix_webhook_is_active"), "webhook", ["is_active"], unique=False)
    op.create_index(
        op.f("ix_webhook_organization_id"), "webhook", ["organization_id"], unique=False
    )

    op.create_table(
        "invoice",
        sa.Column("organization_id", app.models.types.GUID(), nullable=False),
        sa.Column("subscription_id", app.models.types.GUID(), nullable=True),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("tax_cents", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("amount_paid_cents", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("line_items", sa.JSON(), nullable=False),
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
            name=op.f("fk_invoice_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscription.id"],
            name=op.f("fk_invoice_subscription_id_subscription"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice")),
    )
    op.create_index(
        op.f("ix_invoice_deleted_at"), "invoice", ["deleted_at"], unique=False
    )
    op.create_index(op.f("ix_invoice_number"), "invoice", ["number"], unique=True)
    op.create_index(
        op.f("ix_invoice_organization_id"), "invoice", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_invoice_status"), "invoice", ["status"], unique=False)
    op.create_index(
        op.f("ix_invoice_subscription_id"), "invoice", ["subscription_id"], unique=False
    )

    op.create_table(
        "usage_record",
        sa.Column("organization_id", app.models.types.GUID(), nullable=False),
        sa.Column("subscription_id", app.models.types.GUID(), nullable=True),
        sa.Column("metric", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=16, scale=6), nullable=False),
        sa.Column("recorded_for", sa.Date(), nullable=False),
        sa.Column("invoiced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_id", app.models.types.GUID(), nullable=True),
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
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_usage_record_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["subscription.id"],
            name=op.f("fk_usage_record_subscription_id_subscription"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_record")),
    )
    op.create_index(
        op.f("ix_usage_record_deleted_at"), "usage_record", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_usage_record_invoiced_at"), "usage_record", ["invoiced_at"], unique=False
    )
    op.create_index(
        op.f("ix_usage_record_metric"), "usage_record", ["metric"], unique=False
    )
    op.create_index(
        op.f("ix_usage_record_organization_id"),
        "usage_record",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_usage_record_recorded_for"),
        "usage_record",
        ["recorded_for"],
        unique=False,
    )
    op.create_index(
        op.f("ix_usage_record_subscription_id"),
        "usage_record",
        ["subscription_id"],
        unique=False,
    )

    op.create_table(
        "webhook_delivery",
        sa.Column("webhook_id", app.models.types.GUID(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.String(length=2048), nullable=True),
        sa.Column("error", sa.String(length=512), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
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
            ["webhook_id"],
            ["webhook.id"],
            name=op.f("fk_webhook_delivery_webhook_id_webhook"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_delivery")),
    )
    op.create_index(
        op.f("ix_webhook_delivery_deleted_at"),
        "webhook_delivery",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webhook_delivery_event_type"),
        "webhook_delivery",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webhook_delivery_next_retry_at"),
        "webhook_delivery",
        ["next_retry_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_webhook_delivery_status"), "webhook_delivery", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_webhook_delivery_webhook_id"),
        "webhook_delivery",
        ["webhook_id"],
        unique=False,
    )

    op.create_table(
        "payment",
        sa.Column("invoice_id", app.models.types.GUID(), nullable=False),
        sa.Column("organization_id", app.models.types.GUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("provider_payment_id", sa.String(length=128), nullable=True),
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
        sa.Column("refunded_cents", sa.Integer(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["invoice_id"],
            ["invoice.id"],
            name=op.f("fk_payment_invoice_id_invoice"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name=op.f("fk_payment_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment")),
        sa.UniqueConstraint(
            "provider_payment_id", name=op.f("uq_payment_provider_payment_id")
        ),
    )
    op.create_index(
        op.f("ix_payment_deleted_at"), "payment", ["deleted_at"], unique=False
    )
    op.create_index(
        op.f("ix_payment_invoice_id"), "payment", ["invoice_id"], unique=False
    )
    op.create_index(
        op.f("ix_payment_organization_id"), "payment", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_payment_status"), "payment", ["status"], unique=False)

    op.create_table(
        "render_job",
        sa.Column("video_id", app.models.types.GUID(), nullable=False),
        sa.Column("organization_id", app.models.types.GUID(), nullable=True),
        sa.Column("queue_job_id", app.models.types.GUID(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("output_key", sa.String(length=1024), nullable=True),
        sa.Column("output_bytes", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("options", sa.JSON(), nullable=False),
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
            name=op.f("fk_render_job_organization_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["queue_job_id"],
            ["queue_job.id"],
            name=op.f("fk_render_job_queue_job_id_queue_job"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["video.id"],
            name=op.f("fk_render_job_video_id_video"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_render_job")),
    )
    op.create_index(
        op.f("ix_render_job_deleted_at"), "render_job", ["deleted_at"], unique=False
    )
    op.create_index(op.f("ix_render_job_kind"), "render_job", ["kind"], unique=False)
    op.create_index(
        op.f("ix_render_job_organization_id"),
        "render_job",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_render_job_queue_job_id"), "render_job", ["queue_job_id"], unique=False
    )
    op.create_index(op.f("ix_render_job_status"), "render_job", ["status"], unique=False)
    op.create_index(
        op.f("ix_render_job_video_id"), "render_job", ["video_id"], unique=False
    )


def downgrade() -> None:
    """Drop the tables introduced by this revision.

    Reverse creation order, so a table is gone before whatever it references.
    Indexes belong to their table and go with it.
    """
    op.drop_table("render_job")
    op.drop_table("payment")
    op.drop_table("webhook_delivery")
    op.drop_table("usage_record")
    op.drop_table("invoice")
    op.drop_table("webhook")
    op.drop_table("subscription")
    op.drop_table("queue_job")
    op.drop_table("notification")
    op.drop_table("cost_record")
    op.drop_table("notification_preference")
    op.drop_table("plan")
