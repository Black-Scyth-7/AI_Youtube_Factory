"""Repositories for billing entities."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select

from app.models.billing import (
    CostRecord,
    Invoice,
    Payment,
    Plan,
    Subscription,
    UsageRecord,
)
from app.models.domain_enums import SubscriptionStatus
from app.repositories.base import BaseRepository


class PlanRepository(BaseRepository[Plan]):
    model = Plan

    async def get_by_code(self, code: str) -> Plan | None:
        return await self.find_by(code=code)

    async def list_public(self) -> list[Plan]:
        stmt = (
            self._base_query().where(Plan.is_public.is_(True)).order_by(Plan.price_cents)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    async def get_active_for_organization(
        self, organization_id: uuid.UUID
    ) -> Subscription | None:
        """Return the subscription currently granting access, if any.

        Trialing counts: access is granted before the first payment.
        """
        stmt = (
            self._base_query()
            .where(
                Subscription.organization_id == organization_id,
                Subscription.status.in_(
                    [SubscriptionStatus.ACTIVE.value, SubscriptionStatus.TRIALING.value]
                ),
            )
            .order_by(Subscription.created_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def list_expiring(self, before: date) -> list[Subscription]:
        stmt = self._base_query().where(
            Subscription.current_period_end <= before,
            Subscription.status == SubscriptionStatus.ACTIVE.value,
        )
        return list((await self.session.execute(stmt)).scalars().all())


class InvoiceRepository(BaseRepository[Invoice]):
    model = Invoice

    async def get_by_number(self, number: str) -> Invoice | None:
        return await self.find_by(number=number)

    async def list_for_organization(
        self, organization_id: uuid.UUID, limit: int = 50
    ) -> list[Invoice]:
        stmt = (
            self._base_query()
            .where(Invoice.organization_id == organization_id)
            .order_by(Invoice.created_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class PaymentRepository(BaseRepository[Payment]):
    model = Payment

    async def get_by_provider_id(self, provider_payment_id: str) -> Payment | None:
        """Look up by the provider's id so a replayed webhook is idempotent."""
        return await self.find_by(provider_payment_id=provider_payment_id)

    async def list_for_invoice(self, invoice_id: uuid.UUID) -> list[Payment]:
        stmt = self._base_query().where(Payment.invoice_id == invoice_id)
        return list((await self.session.execute(stmt)).scalars().all())


class UsageRecordRepository(BaseRepository[UsageRecord]):
    model = UsageRecord

    async def list_uninvoiced(
        self, organization_id: uuid.UUID, until: date
    ) -> list[UsageRecord]:
        """Usage not yet rolled into an invoice, up to and including ``until``."""
        stmt = self._base_query().where(
            UsageRecord.organization_id == organization_id,
            UsageRecord.recorded_for <= until,
            UsageRecord.invoiced_at.is_(None),
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def total_for_metric(
        self, organization_id: uuid.UUID, metric: str, since: date
    ) -> float:
        stmt = select(UsageRecord.quantity).where(
            UsageRecord.organization_id == organization_id,
            UsageRecord.metric == metric,
            UsageRecord.recorded_for >= since,
            UsageRecord.deleted_at.is_(None),
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return float(sum(rows)) if rows else 0.0


class CostRecordRepository(BaseRepository[CostRecord]):
    model = CostRecord

    async def list_for_day(self, incurred_on: date) -> list[CostRecord]:
        stmt = self._base_query().where(CostRecord.incurred_on == incurred_on)
        return list((await self.session.execute(stmt)).scalars().all())
