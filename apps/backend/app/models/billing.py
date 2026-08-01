"""Billing models: plans, subscriptions, invoices, and payments.

Monetary amounts are stored as integer **minor units** (cents), never floats —
binary floating point cannot represent decimal currency exactly. Rates that are
genuinely fractional (per-unit overage prices) use ``Numeric``, matching the
LLM cost columns.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.domain_enums import (
    BillingInterval,
    InvoiceStatus,
    PaymentStatus,
    SubscriptionStatus,
)
from app.models.mixins import EntityMixin
from app.models.types import GUID


class Plan(EntityMixin, Base):
    """A purchasable plan. Quotas are the ceilings enforced against usage."""

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    interval: Mapped[str] = mapped_column(
        String(16), default=BillingInterval.MONTHLY.value, nullable=False
    )
    trial_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Quotas: metric name -> allowance per billing period. Absent means unlimited.
    quotas: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    # Per-unit price charged once a quota is exceeded, keyed by the same metric.
    overage_rates: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    features: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    subscriptions: Mapped[list[Subscription]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class Subscription(EntityMixin, Base):
    """An organization's subscription to a plan for a billing period."""

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "status", name="uq_subscription_organization_id_status"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("plan.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), default=SubscriptionStatus.TRIALING.value, nullable=False, index=True
    )
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    trial_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Set when the customer cancels but keeps access until the period ends.
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    external_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)

    plan: Mapped[Plan] = relationship(back_populates="subscriptions")
    invoices: Mapped[list[Invoice]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )


class Invoice(EntityMixin, Base):
    """An issued invoice for one billing period."""

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("subscription.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    number: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default=InvoiceStatus.DRAFT.value, nullable=False, index=True
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tax_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount_paid_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Frozen line items: [{description, quantity, unit_price_cents, amount_cents}]
    line_items: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )

    subscription: Mapped[Subscription | None] = relationship(back_populates="invoices")
    payments: Mapped[list[Payment]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )

    @property
    def amount_due_cents(self) -> int:
        """Outstanding balance; never negative."""
        return max(self.total_cents - self.amount_paid_cents, 0)


class Payment(EntityMixin, Base):
    """A payment attempt against an invoice."""

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("invoice.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16), default=PaymentStatus.PENDING.value, nullable=False, index=True
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Provider-side id; unique so a webhook replay cannot double-record a payment.
    provider_payment_id: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    refunded_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    invoice: Mapped[Invoice] = relationship(back_populates="payments")


class UsageRecord(EntityMixin, Base):
    """A metered usage event, aggregated into invoices at period close."""

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("subscription.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    metric: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(16, 6), default=Decimal("0"), nullable=False
    )
    recorded_for: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # Set once the record has been rolled into an invoice, so it is billed once.
    invoiced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )


class CostRecord(EntityMixin, Base):
    """Internal cost of serving a request — what we pay, not what we charge."""

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("organization.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    vendor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0"), nullable=False
    )
    incurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
