"""Charging invoices through a payment provider, and handling callbacks.

Sits between :mod:`app.services.billing`, which owns invoice and payment state,
and :mod:`app.core.payments`, which talks to a processor. Keeping them apart
means the billing rules are testable without a provider and a provider can be
added without touching them.

Two properties matter more than anything else here:

* **Idempotency.** Providers retry callbacks until they get a 2xx, so the same
  event arrives repeatedly by design. Every write keys off the provider's own
  id, and a repeat returns the original record rather than paying twice.
* **A decline is not an error.** It is an outcome the caller must be told
  about, so it comes back as a result rather than an exception. Only a broken
  provider raises.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.payments import (
    ChargeStatus,
    PaymentProviderError,
    WebhookEvent,
    get_provider,
)
from app.exceptions.base import NotFoundError, ValidationError
from app.logging import get_logger
from app.models.billing import Invoice, Payment
from app.models.domain_enums import InvoiceStatus
from app.observability import instruments
from app.observability.tracing import start_span
from app.repositories.billing import InvoiceRepository, PaymentRepository
from app.services.billing import PaymentService

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ChargeOutcome:
    """The result of attempting to collect an invoice."""

    status: ChargeStatus
    invoice: Invoice
    amount_cents: int
    payment: Payment | None = None
    decline_reason: str | None = None
    action_url: str | None = None


class PaymentGatewayService:
    """Collects invoices and applies provider callbacks."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.invoices = InvoiceRepository(session)
        self.payments = PaymentRepository(session)
        self.payment_service = PaymentService(session)

    @staticmethod
    def amount_due(invoice: Invoice) -> int:
        """What is still owed, never negative."""
        return max(invoice.total_cents - invoice.amount_paid_cents, 0)

    async def charge_invoice(
        self,
        invoice_id: uuid.UUID,
        *,
        provider_slug: str | None = None,
        customer_reference: str | None = None,
    ) -> ChargeOutcome:
        """Attempt to collect an invoice in full.

        Raises:
            NotFoundError: If the invoice does not exist.
            ValidationError: If there is nothing to collect, or the invoice was
                voided. Charging a voided invoice is always a mistake.
        """
        invoice = await self.invoices.get(invoice_id)
        if invoice is None:
            raise NotFoundError("Invoice not found.")
        if invoice.status == InvoiceStatus.VOID.value:
            raise ValidationError("This invoice was voided and cannot be paid.")

        due = self.amount_due(invoice)
        if due <= 0:
            raise ValidationError("This invoice has nothing left to pay.")

        provider = get_provider(provider_slug)
        with start_span(
            "payments.charge",
            kind="client",
            attributes={"payment.provider": provider.slug, "payment.amount": due},
        ):
            result = await provider.charge(
                amount_cents=due,
                currency=invoice.currency,
                # The invoice number, not its id: it is what appears on a bank
                # statement and what a human quotes when disputing a charge.
                reference=invoice.number,
                customer_reference=customer_reference,
                metadata={"organization_id": str(invoice.organization_id)},
            )

        instruments.payments_total.inc(
            1.0, provider=provider.slug, outcome=result.status.value
        )

        if not result.succeeded:
            logger.warning(
                "payment.not_settled",
                extra={
                    "invoice": invoice.number,
                    "provider": provider.slug,
                    "status": result.status.value,
                    "reason": result.decline_reason,
                },
            )
            return ChargeOutcome(
                status=result.status,
                invoice=invoice,
                amount_cents=due,
                decline_reason=result.decline_reason,
                action_url=result.action_url,
            )

        payment = await self.payment_service.record_payment(
            invoice.id,
            result.amount_cents,
            provider=provider.slug,
            provider_payment_id=result.provider_payment_id,
        )
        instruments.payments_collected_cents_total.inc(
            float(result.amount_cents), provider=provider.slug
        )
        logger.info(
            "payment.settled",
            extra={
                "invoice": invoice.number,
                "provider": provider.slug,
                "amount_cents": result.amount_cents,
            },
        )
        return ChargeOutcome(
            status=result.status,
            invoice=invoice,
            amount_cents=result.amount_cents,
            payment=payment,
        )

    async def refund_payment(
        self, payment_id: uuid.UUID, amount_cents: int | None = None
    ) -> Payment:
        """Refund a settled payment through the provider that took it.

        The provider is called first: recording a refund the processor never
        made would leave the ledger claiming money was returned when it was not.
        """
        payment = await self.payments.get(payment_id)
        if payment is None:
            raise NotFoundError("Payment not found.")

        refundable = payment.amount_cents - payment.refunded_cents
        amount = refundable if amount_cents is None else amount_cents
        if amount <= 0 or amount > refundable:
            raise ValidationError(
                f"Refund must be between 1 and {refundable} cents.",
                details={"refundable_cents": refundable},
            )
        if not payment.provider_payment_id:
            raise ValidationError(
                "This payment has no provider reference and cannot be refunded "
                "automatically."
            )

        provider = get_provider(payment.provider)
        with start_span(
            "payments.refund",
            kind="client",
            attributes={"payment.provider": provider.slug, "payment.amount": amount},
        ):
            await provider.refund(
                provider_payment_id=payment.provider_payment_id, amount_cents=amount
            )

        instruments.payments_total.inc(1.0, provider=provider.slug, outcome="refunded")
        return await self.payment_service.refund(payment.id, amount)

    async def handle_webhook(
        self, *, payload: bytes, signature: str | None, provider_slug: str | None = None
    ) -> WebhookEvent:
        """Verify and apply a provider callback.

        Verification happens against the raw request body. A callback moves
        money, so an unverified one is an unauthenticated request to do so and
        is refused before anything is read out of it.

        Raises:
            PaymentProviderError: If the signature is missing or wrong.
        """
        from app.config import settings

        provider = get_provider(provider_slug)
        event = provider.verify_webhook(
            payload=payload,
            signature=signature,
            secret=settings.payment_webhook_secret,
        )

        instruments.payment_webhooks_total.inc(
            1.0, provider=provider.slug, event_type=event.event_type
        )

        if event.event_type == "payment.succeeded":
            await self._apply_settlement(provider.slug, event)
        else:
            # Unknown types are acknowledged, not rejected: a provider that
            # gets a 4xx retries forever, and a new event type it decided to
            # send is not this system's failure.
            logger.info(
                "payment.webhook_ignored",
                extra={"provider": provider.slug, "event_type": event.event_type},
            )
        return event

    async def _apply_settlement(self, provider_slug: str, event: WebhookEvent) -> None:
        """Record a settlement the provider reported out of band."""
        if not event.provider_payment_id or event.amount_cents is None:
            raise ValidationError(
                "A payment.succeeded callback needs provider_payment_id and "
                "amount_cents.",
                details={"event_id": event.event_id},
            )

        existing = await self.payments.get_by_provider_id(event.provider_payment_id)
        if existing is not None:
            logger.info(
                "payment.webhook_replayed",
                extra={"provider": provider_slug, "event_id": event.event_id},
            )
            return

        number = str(event.payload.get("data", {}).get("reference") or "")
        invoice = await self.invoices.get_by_number(number) if number else None
        if invoice is None:
            raise NotFoundError(
                "The callback references an unknown invoice.",
                details={"reference": number, "event_id": event.event_id},
            )

        await self.payment_service.record_payment(
            invoice.id,
            event.amount_cents,
            provider=provider_slug,
            provider_payment_id=event.provider_payment_id,
        )
        instruments.payments_collected_cents_total.inc(
            float(event.amount_cents), provider=provider_slug
        )


__all__ = ["ChargeOutcome", "PaymentGatewayService", "PaymentProviderError"]
