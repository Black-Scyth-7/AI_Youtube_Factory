"""Billing services: plans, subscriptions, metered usage, and invoicing.

Amounts are integer minor units (cents) throughout. Rounding happens once, at
the point a fractional usage total becomes a charge, and uses ROUND_HALF_UP so
a half-cent is never silently dropped in the customer's favour or ours.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.models.billing import (
    CostRecord,
    Invoice,
    Payment,
    Plan,
    Subscription,
    UsageRecord,
)
from app.models.domain_enums import (
    BillingInterval,
    InvoiceStatus,
    PaymentStatus,
    SubscriptionStatus,
)
from app.repositories.billing import (
    CostRecordRepository,
    InvoiceRepository,
    PaymentRepository,
    PlanRepository,
    SubscriptionRepository,
    UsageRecordRepository,
)


def _period_end(start: datetime, interval: str) -> datetime:
    """End of the billing period beginning at ``start``.

    Uses a 30/365-day step rather than calendar arithmetic so every period has a
    predictable length; calendar months would make usage rates uneven.
    """
    if interval == BillingInterval.YEARLY.value:
        return start + timedelta(days=365)
    return start + timedelta(days=30)


class PlanService:
    """Reads the plan catalogue."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PlanRepository(session)

    async def list_public(self) -> list[Plan]:
        return await self.repo.list_public()

    async def get_by_code(self, code: str) -> Plan:
        plan = await self.repo.get_by_code(code)
        if plan is None:
            raise NotFoundError("Plan not found.", details={"code": code})
        return plan


class SubscriptionService:
    """Creates, cancels and inspects organization subscriptions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SubscriptionRepository(session)
        self.plans = PlanRepository(session)

    async def subscribe(self, organization_id: uuid.UUID, plan_code: str) -> Subscription:
        """Start a subscription, honouring the plan's trial period."""
        plan = await self.plans.get_by_code(plan_code)
        if plan is None:
            raise NotFoundError("Plan not found.", details={"code": plan_code})

        existing = await self.repo.get_active_for_organization(organization_id)
        if existing is not None:
            raise ConflictError(
                "That organization already has an active subscription.",
                details={"subscription_id": str(existing.id)},
            )

        now = datetime.now(UTC)
        trialing = plan.trial_days > 0
        subscription = Subscription(
            organization_id=organization_id,
            plan_id=plan.id,
            status=(
                SubscriptionStatus.TRIALING.value
                if trialing
                else SubscriptionStatus.ACTIVE.value
            ),
            current_period_start=now,
            current_period_end=_period_end(now, plan.interval),
            trial_ends_at=now + timedelta(days=plan.trial_days) if trialing else None,
        )
        return await self.repo.add(subscription)

    async def cancel(
        self, subscription_id: uuid.UUID, *, at_period_end: bool = True
    ) -> Subscription:
        """Cancel a subscription, immediately or at the end of the period."""
        subscription = await self.repo.get(subscription_id)
        if subscription is None:
            raise NotFoundError("Subscription not found.")

        subscription.cancelled_at = datetime.now(UTC)
        subscription.cancel_at_period_end = at_period_end
        if not at_period_end:
            subscription.status = SubscriptionStatus.CANCELLED.value
        await self.session.flush()
        return subscription

    async def get_active(self, organization_id: uuid.UUID) -> Subscription | None:
        return await self.repo.get_active_for_organization(organization_id)


class UsageService:
    """Records metered usage and answers quota questions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UsageRecordRepository(session)
        self.subscriptions = SubscriptionRepository(session)
        self.plans = PlanRepository(session)

    async def record(
        self,
        organization_id: uuid.UUID,
        metric: str,
        quantity: Decimal | int | float,
        *,
        source_type: str | None = None,
        source_id: uuid.UUID | None = None,
        on: date | None = None,
    ) -> UsageRecord:
        amount = Decimal(str(quantity))
        if amount < 0:
            raise ValidationError("Usage quantity cannot be negative.")

        subscription = await self.subscriptions.get_active_for_organization(
            organization_id
        )
        record = UsageRecord(
            organization_id=organization_id,
            subscription_id=subscription.id if subscription else None,
            metric=metric,
            quantity=amount,
            recorded_for=on or datetime.now(UTC).date(),
            source_type=source_type,
            source_id=source_id,
        )
        return await self.repo.add(record)

    async def quota_remaining(
        self, organization_id: uuid.UUID, metric: str
    ) -> Decimal | None:
        """Allowance left this period. ``None`` means unlimited or no plan."""
        subscription = await self.subscriptions.get_active_for_organization(
            organization_id
        )
        if subscription is None:
            return None
        plan = await self.plans.get(subscription.plan_id)
        if plan is None or metric not in plan.quotas:
            return None

        allowance = Decimal(str(plan.quotas[metric]))
        used = Decimal(
            str(
                await self.repo.total_for_metric(
                    organization_id, metric, subscription.current_period_start.date()
                )
            )
        )
        return allowance - used

    async def is_within_quota(self, organization_id: uuid.UUID, metric: str) -> bool:
        remaining = await self.quota_remaining(organization_id, metric)
        return remaining is None or remaining > 0


class InvoiceService:
    """Builds invoices from a plan's fee plus any metered overage."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = InvoiceRepository(session)
        self.usage = UsageRecordRepository(session)
        self.subscriptions = SubscriptionRepository(session)
        self.plans = PlanRepository(session)

    @staticmethod
    def _number_for(when: datetime, sequence: int) -> str:
        return f"INV-{when:%Y%m}-{sequence:06d}"

    async def _next_number(self, when: datetime) -> str:
        """Sequential per month. Collisions raise rather than overwrite."""
        prefix = f"INV-{when:%Y%m}-"
        existing = await self.repo.count()
        candidate = self._number_for(when, existing + 1)
        if await self.repo.get_by_number(candidate) is not None:
            raise ConflictError(
                "Invoice number already used.", details={"number": candidate}
            )
        assert candidate.startswith(prefix)
        return candidate

    async def close_period(self, subscription_id: uuid.UUID) -> Invoice:
        """Close the current period: charge the plan fee plus overage.

        Usage rows are stamped ``invoiced_at`` so a second call cannot bill the
        same usage twice.
        """
        subscription = await self.subscriptions.get(subscription_id)
        if subscription is None:
            raise NotFoundError("Subscription not found.")
        plan = await self.plans.get(subscription.plan_id)
        if plan is None:
            raise NotFoundError("Plan not found.")

        period_start = subscription.current_period_start.date()
        period_end = subscription.current_period_end.date()

        line_items: list[dict[str, object]] = [
            {
                "description": f"{plan.name} ({plan.interval})",
                "quantity": 1,
                "unit_price_cents": plan.price_cents,
                "amount_cents": plan.price_cents,
            }
        ]
        subtotal = plan.price_cents

        usage_rows = await self.usage.list_uninvoiced(
            subscription.organization_id, period_end
        )
        totals: dict[str, Decimal] = {}
        for row in usage_rows:
            totals[row.metric] = totals.get(row.metric, Decimal("0")) + row.quantity

        for metric, used in sorted(totals.items()):
            allowance = Decimal(str(plan.quotas.get(metric, 0)))
            over = used - allowance
            rate = plan.overage_rates.get(metric)
            if over <= 0 or rate is None:
                continue
            amount = (over * Decimal(str(rate))).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            line_items.append(
                {
                    "description": f"{metric} overage",
                    "quantity": float(over),
                    "unit_price_cents": float(rate),
                    "amount_cents": int(amount),
                }
            )
            subtotal += int(amount)

        now = datetime.now(UTC)
        invoice = Invoice(
            organization_id=subscription.organization_id,
            subscription_id=subscription.id,
            number=await self._next_number(now),
            status=InvoiceStatus.OPEN.value,
            currency=plan.currency,
            subtotal_cents=subtotal,
            tax_cents=0,
            total_cents=subtotal,
            period_start=period_start,
            period_end=period_end,
            issued_at=now,
            due_at=now + timedelta(days=14),
            line_items=line_items,
        )
        await self.repo.add(invoice)

        for row in usage_rows:
            row.invoiced_at = now
        await self.session.flush()
        return invoice

    async def list_for_organization(self, organization_id: uuid.UUID) -> list[Invoice]:
        return await self.repo.list_for_organization(organization_id)


class PaymentService:
    """Records payments and keeps the parent invoice's balance in step."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = PaymentRepository(session)
        self.invoices = InvoiceRepository(session)

    async def record_payment(
        self,
        invoice_id: uuid.UUID,
        amount_cents: int,
        *,
        provider: str | None = None,
        provider_payment_id: str | None = None,
    ) -> Payment:
        """Record a successful payment.

        Idempotent on ``provider_payment_id``: a replayed provider webhook
        returns the original payment instead of charging the invoice twice.
        """
        if amount_cents <= 0:
            raise ValidationError("Payment amount must be positive.")

        if provider_payment_id:
            existing = await self.repo.get_by_provider_id(provider_payment_id)
            if existing is not None:
                return existing

        invoice = await self.invoices.get(invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found.")

        payment = Payment(
            invoice_id=invoice.id,
            organization_id=invoice.organization_id,
            status=PaymentStatus.SUCCEEDED.value,
            amount_cents=amount_cents,
            currency=invoice.currency,
            provider=provider,
            provider_payment_id=provider_payment_id,
            processed_at=datetime.now(UTC),
        )
        await self.repo.add(payment)

        invoice.amount_paid_cents += amount_cents
        if invoice.amount_paid_cents >= invoice.total_cents:
            invoice.status = InvoiceStatus.PAID.value
            invoice.paid_at = datetime.now(UTC)
        await self.session.flush()
        return payment

    async def refund(self, payment_id: uuid.UUID, amount_cents: int) -> Payment:
        payment = await self.repo.get(payment_id)
        if payment is None:
            raise NotFoundError("Payment not found.")
        if amount_cents <= 0:
            raise ValidationError("Refund amount must be positive.")
        if payment.refunded_cents + amount_cents > payment.amount_cents:
            raise ValidationError("Refund exceeds the amount paid.")

        payment.refunded_cents += amount_cents
        if payment.refunded_cents == payment.amount_cents:
            payment.status = PaymentStatus.REFUNDED.value

        invoice = await self.invoices.get(payment.invoice_id)
        if invoice is not None:
            invoice.amount_paid_cents = max(invoice.amount_paid_cents - amount_cents, 0)
            if invoice.amount_paid_cents < invoice.total_cents:
                invoice.status = InvoiceStatus.OPEN.value
                invoice.paid_at = None
        await self.session.flush()
        return payment


class CostService:
    """Records internal cost of service — what we pay, not what we charge."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CostRecordRepository(session)

    async def record(
        self,
        category: str,
        amount_usd: Decimal | float | str,
        *,
        organization_id: uuid.UUID | None = None,
        vendor: str | None = None,
        on: date | None = None,
    ) -> CostRecord:
        amount = Decimal(str(amount_usd))
        if amount < 0:
            raise ValidationError("Cost amount cannot be negative.")
        record = CostRecord(
            organization_id=organization_id,
            category=category,
            vendor=vendor,
            amount_usd=amount,
            incurred_on=on or datetime.now(UTC).date(),
        )
        return await self.repo.add(record)
