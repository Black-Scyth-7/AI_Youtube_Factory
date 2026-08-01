"""Tests for collecting invoices through a payment provider.

The properties worth protecting are idempotency — providers retry, so the same
charge and the same callback arrive more than once by design — and that a
decline is reported rather than raised.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime

import pytest
from app.core.payments import ChargeStatus, MockPaymentProvider, PaymentProviderError
from app.exceptions.base import NotFoundError, ValidationError
from app.models.billing import Invoice, Payment
from app.models.domain_enums import InvoiceStatus, PaymentStatus
from app.services.payment_gateway import PaymentGatewayService
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio

SECRET = "webhook-secret-for-tests"


async def _make_invoice(
    session: AsyncSession,
    *,
    number: str = "INV-2026-0001",
    total_cents: int = 5000,
    paid_cents: int = 0,
    status: str = InvoiceStatus.OPEN.value,
) -> Invoice:
    invoice = Invoice(
        organization_id=uuid.uuid4(),
        number=number,
        status=status,
        currency="USD",
        subtotal_cents=total_cents,
        total_cents=total_cents,
        amount_paid_cents=paid_cents,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    session.add(invoice)
    await session.flush()
    return invoice


# -- Charging -----------------------------------------------------------------


async def test_a_settled_charge_pays_the_invoice(session: AsyncSession) -> None:
    invoice = await _make_invoice(session, total_cents=5000)
    outcome = await PaymentGatewayService(session).charge_invoice(invoice.id)

    assert outcome.status is ChargeStatus.SUCCEEDED
    assert outcome.payment is not None
    assert outcome.payment.status == PaymentStatus.SUCCEEDED.value
    assert outcome.payment.provider == "mock"
    assert invoice.amount_paid_cents == 5000
    assert invoice.status == InvoiceStatus.PAID.value
    assert invoice.paid_at is not None


async def test_only_the_outstanding_balance_is_charged(session: AsyncSession) -> None:
    """A partly-paid invoice must not be charged its full total again."""
    invoice = await _make_invoice(session, total_cents=5000, paid_cents=2000)
    outcome = await PaymentGatewayService(session).charge_invoice(invoice.id)

    assert outcome.amount_cents == 3000
    assert invoice.amount_paid_cents == 5000
    assert invoice.status == InvoiceStatus.PAID.value


async def test_charging_the_same_invoice_twice_does_not_double_charge(
    session: AsyncSession,
) -> None:
    """The provider returns a stable id for an identical request, and the
    service keys off it, so a retried request settles once."""
    invoice = await _make_invoice(session, total_cents=5000)
    gateway = PaymentGatewayService(session)

    first = await gateway.charge_invoice(invoice.id)
    assert invoice.amount_paid_cents == 5000

    # The second attempt is refused because nothing is outstanding — the guard
    # before the provider is ever called.
    with pytest.raises(ValidationError, match="nothing left to pay"):
        await gateway.charge_invoice(invoice.id)

    payments = await gateway.payments.list_for_invoice(invoice.id)
    assert len(payments) == 1
    assert payments[0].id == first.payment.id  # type: ignore[union-attr]


async def test_a_decline_is_reported_and_leaves_the_invoice_unpaid(
    session: AsyncSession,
) -> None:
    invoice = await _make_invoice(session, number="INV-decline-2026", total_cents=5000)
    outcome = await PaymentGatewayService(session).charge_invoice(invoice.id)

    assert outcome.status is ChargeStatus.DECLINED
    assert outcome.decline_reason == "card_declined"
    assert outcome.payment is None
    assert invoice.amount_paid_cents == 0
    assert invoice.status == InvoiceStatus.OPEN.value


async def test_a_charge_requiring_action_does_not_record_a_payment(
    session: AsyncSession,
) -> None:
    invoice = await _make_invoice(session, number="INV-requires-action-1")
    outcome = await PaymentGatewayService(session).charge_invoice(invoice.id)

    assert outcome.status is ChargeStatus.REQUIRES_ACTION
    assert outcome.action_url
    assert outcome.payment is None
    assert invoice.amount_paid_cents == 0


async def test_a_fully_paid_invoice_cannot_be_charged(session: AsyncSession) -> None:
    invoice = await _make_invoice(session, total_cents=5000, paid_cents=5000)
    with pytest.raises(ValidationError, match="nothing left to pay"):
        await PaymentGatewayService(session).charge_invoice(invoice.id)


async def test_a_voided_invoice_cannot_be_charged(session: AsyncSession) -> None:
    """Collecting against a voided invoice is always a mistake."""
    invoice = await _make_invoice(session, status=InvoiceStatus.VOID.value)
    with pytest.raises(ValidationError, match="voided"):
        await PaymentGatewayService(session).charge_invoice(invoice.id)


async def test_charging_an_unknown_invoice_raises(session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await PaymentGatewayService(session).charge_invoice(uuid.uuid4())


# -- Refunds ------------------------------------------------------------------


async def test_a_payment_can_be_refunded_in_full(session: AsyncSession) -> None:
    invoice = await _make_invoice(session, total_cents=5000)
    gateway = PaymentGatewayService(session)
    outcome = await gateway.charge_invoice(invoice.id)
    assert outcome.payment is not None

    refunded = await gateway.refund_payment(outcome.payment.id)
    assert refunded.refunded_cents == 5000


async def test_a_partial_refund_leaves_the_rest_refundable(
    session: AsyncSession,
) -> None:
    invoice = await _make_invoice(session, total_cents=5000)
    gateway = PaymentGatewayService(session)
    outcome = await gateway.charge_invoice(invoice.id)
    assert outcome.payment is not None

    await gateway.refund_payment(outcome.payment.id, 2000)
    again = await gateway.refund_payment(outcome.payment.id, 3000)
    assert again.refunded_cents == 5000


async def test_refunding_more_than_was_paid_is_rejected(
    session: AsyncSession,
) -> None:
    """Otherwise the ledger claims more money was returned than was taken."""
    invoice = await _make_invoice(session, total_cents=5000)
    gateway = PaymentGatewayService(session)
    outcome = await gateway.charge_invoice(invoice.id)
    assert outcome.payment is not None

    with pytest.raises(ValidationError, match="between 1 and 5000"):
        await gateway.refund_payment(outcome.payment.id, 6000)


async def test_a_payment_without_a_provider_reference_cannot_be_auto_refunded(
    session: AsyncSession,
) -> None:
    """A manually recorded payment has nothing for the provider to reverse."""
    invoice = await _make_invoice(session)
    payment = Payment(
        invoice_id=invoice.id,
        organization_id=invoice.organization_id,
        status=PaymentStatus.SUCCEEDED.value,
        amount_cents=5000,
        currency="USD",
        provider=None,
        provider_payment_id=None,
        processed_at=datetime.now(UTC),
    )
    session.add(payment)
    await session.flush()

    with pytest.raises(ValidationError, match="no provider reference"):
        await PaymentGatewayService(session).refund_payment(payment.id)


# -- Webhooks -----------------------------------------------------------------


def _signed(body: dict[str, object]) -> tuple[bytes, str]:
    payload = json.dumps(body).encode()
    return payload, MockPaymentProvider.sign(payload, SECRET)


@pytest.fixture()
def webhook_secret(monkeypatch: pytest.MonkeyPatch) -> str:
    from app.config import settings

    monkeypatch.setattr(settings, "payment_webhook_secret", SECRET)
    return SECRET


async def test_a_settlement_callback_pays_the_invoice(
    session: AsyncSession, webhook_secret: str
) -> None:
    invoice = await _make_invoice(session, number="INV-2026-0777", total_cents=4200)
    payload, signature = _signed(
        {
            "id": "evt_1",
            "type": "payment.succeeded",
            "data": {
                "provider_payment_id": "mockpay_external",
                "amount_cents": 4200,
                "reference": invoice.number,
            },
        }
    )

    await PaymentGatewayService(session).handle_webhook(
        payload=payload, signature=signature
    )

    assert invoice.amount_paid_cents == 4200
    assert invoice.status == InvoiceStatus.PAID.value


async def test_a_replayed_callback_does_not_pay_twice(
    session: AsyncSession, webhook_secret: str
) -> None:
    """Providers retry until they get a 2xx, so the same event arrives again."""
    invoice = await _make_invoice(session, number="INV-2026-0778", total_cents=4200)
    payload, signature = _signed(
        {
            "id": "evt_2",
            "type": "payment.succeeded",
            "data": {
                "provider_payment_id": "mockpay_replay",
                "amount_cents": 4200,
                "reference": invoice.number,
            },
        }
    )
    gateway = PaymentGatewayService(session)

    await gateway.handle_webhook(payload=payload, signature=signature)
    await gateway.handle_webhook(payload=payload, signature=signature)

    assert invoice.amount_paid_cents == 4200
    assert len(await gateway.payments.list_for_invoice(invoice.id)) == 1


async def test_an_unsigned_callback_is_refused(
    session: AsyncSession, webhook_secret: str
) -> None:
    payload, _ = _signed({"id": "evt_3", "type": "payment.succeeded", "data": {}})
    with pytest.raises(PaymentProviderError):
        await PaymentGatewayService(session).handle_webhook(
            payload=payload, signature=None
        )


async def test_a_callback_for_an_unknown_invoice_raises(
    session: AsyncSession, webhook_secret: str
) -> None:
    payload, signature = _signed(
        {
            "id": "evt_4",
            "type": "payment.succeeded",
            "data": {
                "provider_payment_id": "mockpay_orphan",
                "amount_cents": 100,
                "reference": "INV-does-not-exist",
            },
        }
    )
    with pytest.raises(NotFoundError, match="unknown invoice"):
        await PaymentGatewayService(session).handle_webhook(
            payload=payload, signature=signature
        )


async def test_an_unknown_event_type_is_acknowledged(
    session: AsyncSession, webhook_secret: str
) -> None:
    """A 4xx would make the provider retry a type this system simply ignores."""
    payload, signature = _signed(
        {"id": "evt_5", "type": "invoice.some_future_thing", "data": {}}
    )
    event = await PaymentGatewayService(session).handle_webhook(
        payload=payload, signature=signature
    )
    assert event.event_type == "invoice.some_future_thing"
