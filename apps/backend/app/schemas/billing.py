"""Billing request and response schemas.

Money crosses the API as integer minor units, named ``*_cents``, and is
formatted for display by the client. Sending a decimal would invite a float on
the other side, and a float cannot hold 0.1.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlanResponse(BaseModel):
    """A purchasable plan."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    price_cents: int
    currency: str
    interval: str
    trial_days: int
    quotas: dict[str, int] = Field(
        default_factory=dict,
        description="Metric name to allowance per period. Absent means unlimited.",
    )
    overage_rates: dict[str, float] = Field(default_factory=dict)
    features: list[str] = Field(default_factory=list)


class SubscribeRequest(BaseModel):
    """Start or change a subscription."""

    plan_code: str = Field(min_length=1, max_length=64)


class SubscriptionResponse(BaseModel):
    """An organization's current subscription."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    plan_id: uuid.UUID
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    trial_ends_at: datetime | None = None
    cancel_at_period_end: bool = False
    #: Spelled as the model spells it. With from_attributes a mismatched name
    #: does not error — the field just stays null forever.
    cancelled_at: datetime | None = None
    external_reference: str | None = None


class CancelSubscriptionRequest(BaseModel):
    """Cancel a subscription."""

    at_period_end: bool = Field(
        default=True,
        description=(
            "Cancel when the paid period ends. False ends access immediately "
            "and does not refund the remainder."
        ),
    )


class InvoiceLineResponse(BaseModel):
    """One charge on an invoice."""

    description: str
    quantity: float
    unit_price_cents: int
    amount_cents: int


class InvoiceResponse(BaseModel):
    """A closed billing period."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    number: str
    status: str
    currency: str
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    amount_paid_cents: int
    period_start: datetime | None = None
    period_end: datetime | None = None
    due_at: datetime | None = None
    paid_at: datetime | None = None
    line_items: list[InvoiceLineResponse] = Field(default_factory=list)

    @property
    def amount_due_cents(self) -> int:
        return max(self.total_cents - self.amount_paid_cents, 0)


class PaymentResponse(BaseModel):
    """A payment attempt against an invoice."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    status: str
    amount_cents: int
    currency: str
    provider: str | None = None
    refunded_cents: int = 0
    failure_reason: str | None = None
    processed_at: datetime | None = None


class PayInvoiceRequest(BaseModel):
    """Collect payment for an invoice."""

    #: Optional: falls back to the configured provider.
    provider: str | None = Field(default=None, max_length=32)
    customer_reference: str | None = Field(default=None, max_length=128)


class PayInvoiceResponse(BaseModel):
    """The outcome of a charge attempt.

    A decline is a 200 with ``status="declined"``, not an HTTP error: the
    request was handled correctly and the client needs the reason, not a stack
    of retries against a card that will keep failing.
    """

    status: str
    invoice_id: uuid.UUID
    amount_cents: int
    payment: PaymentResponse | None = None
    decline_reason: str | None = None
    action_url: str | None = None


class UsageQuotaResponse(BaseModel):
    """Consumption against a plan's allowance for one metric."""

    metric: str
    used: float
    limit: int | None = Field(
        default=None, description="None means the plan does not cap this metric."
    )
    remaining: int | None = None
    exceeded: bool = False


class UsageSummaryResponse(BaseModel):
    """Everything metered in the current period."""

    organization_id: uuid.UUID
    period_start: datetime | None = None
    period_end: datetime | None = None
    metrics: list[UsageQuotaResponse] = Field(default_factory=list)
