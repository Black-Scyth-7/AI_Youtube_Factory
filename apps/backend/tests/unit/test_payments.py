"""Tests for the payment provider contract and the mock implementation."""

from __future__ import annotations

import json

import pytest
from app.core.payments import (
    ChargeStatus,
    MockPaymentProvider,
    PaymentProvider,
    PaymentProviderError,
    available_providers,
    get_provider,
    register_provider,
    reset_providers,
)

SECRET = "webhook-secret-for-tests"


@pytest.fixture(autouse=True)
def _clean_registry() -> None:
    reset_providers()


# -- Registry -----------------------------------------------------------------


def test_the_mock_is_always_available() -> None:
    """Billing must work out of the box; no test should need a payment account."""
    assert "mock" in available_providers()
    assert get_provider().slug == "mock"


def test_the_mock_satisfies_the_protocol() -> None:
    assert isinstance(MockPaymentProvider(), PaymentProvider)


def test_an_unregistered_provider_is_refused() -> None:
    from app.exceptions.base import ServiceUnavailableError

    with pytest.raises(ServiceUnavailableError, match="stripe"):
        get_provider("stripe")


def test_a_registered_provider_is_resolvable() -> None:
    register_provider("fake", MockPaymentProvider)
    assert get_provider("fake") is not None
    assert "fake" in available_providers()


# -- Charging -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_charge_settles() -> None:
    result = await MockPaymentProvider().charge(
        amount_cents=2500, currency="USD", reference="INV-2026-0001"
    )
    assert result.status is ChargeStatus.SUCCEEDED
    assert result.succeeded is True
    assert result.amount_cents == 2500
    assert result.provider_payment_id.startswith("mockpay_")


@pytest.mark.asyncio
async def test_the_provider_payment_id_is_stable_for_the_same_charge() -> None:
    """Idempotency in the service keys off this id. Random ids per attempt would
    satisfy the test without the guarantee ever holding."""
    provider = MockPaymentProvider()
    first = await provider.charge(
        amount_cents=2500, currency="USD", reference="INV-2026-0001"
    )
    second = await provider.charge(
        amount_cents=2500, currency="USD", reference="INV-2026-0001"
    )
    assert first.provider_payment_id == second.provider_payment_id

    other = await provider.charge(
        amount_cents=2500, currency="USD", reference="INV-2026-0002"
    )
    assert other.provider_payment_id != first.provider_payment_id


@pytest.mark.asyncio
async def test_a_decline_is_a_result_not_an_exception() -> None:
    """A declined card is the provider working; only a broken provider raises."""
    result = await MockPaymentProvider().charge(
        amount_cents=2500, currency="USD", reference="INV-decline-me"
    )
    assert result.status is ChargeStatus.DECLINED
    assert result.succeeded is False
    assert result.decline_reason == "card_declined"


@pytest.mark.asyncio
async def test_a_charge_can_require_further_action() -> None:
    result = await MockPaymentProvider().charge(
        amount_cents=2500, currency="USD", reference="INV-requires-action"
    )
    assert result.status is ChargeStatus.REQUIRES_ACTION
    assert result.action_url


@pytest.mark.asyncio
async def test_a_non_positive_charge_is_rejected() -> None:
    with pytest.raises(PaymentProviderError, match="positive"):
        await MockPaymentProvider().charge(
            amount_cents=0, currency="USD", reference="INV-1"
        )


@pytest.mark.asyncio
async def test_a_refund_returns_a_reference() -> None:
    result = await MockPaymentProvider().refund(
        provider_payment_id="mockpay_abc", amount_cents=500
    )
    assert result.provider_refund_id.startswith("mockref_")
    assert result.amount_cents == 500


# -- Webhook verification -----------------------------------------------------


def _event(**data: object) -> bytes:
    return json.dumps({"id": "evt_1", "type": "payment.succeeded", "data": data}).encode()


def test_a_valid_signature_is_accepted() -> None:
    provider = MockPaymentProvider()
    payload = _event(provider_payment_id="mockpay_abc", amount_cents=2500)
    event = provider.verify_webhook(
        payload=payload, signature=provider.sign(payload, SECRET), secret=SECRET
    )
    assert event.event_id == "evt_1"
    assert event.event_type == "payment.succeeded"
    assert event.provider_payment_id == "mockpay_abc"
    assert event.amount_cents == 2500


def test_a_wrong_signature_is_refused() -> None:
    """A callback moves money; an unverified one is an unauthenticated request
    to do so."""
    provider = MockPaymentProvider()
    payload = _event(provider_payment_id="mockpay_abc", amount_cents=2500)
    with pytest.raises(PaymentProviderError, match="does not match"):
        provider.verify_webhook(payload=payload, signature="deadbeef", secret=SECRET)


def test_a_missing_signature_is_refused() -> None:
    provider = MockPaymentProvider()
    with pytest.raises(PaymentProviderError, match="Missing"):
        provider.verify_webhook(payload=_event(), signature=None, secret=SECRET)


def test_verification_without_a_configured_secret_is_refused() -> None:
    """Empty secret must fail closed. Signing with "" would verify anything."""
    provider = MockPaymentProvider()
    payload = _event()
    with pytest.raises(PaymentProviderError, match="No webhook secret"):
        provider.verify_webhook(
            payload=payload, signature=provider.sign(payload, ""), secret=""
        )


def test_a_tampered_body_fails_verification() -> None:
    provider = MockPaymentProvider()
    payload = _event(provider_payment_id="mockpay_abc", amount_cents=2500)
    signature = provider.sign(payload, SECRET)
    tampered = payload.replace(b"2500", b"9900")

    with pytest.raises(PaymentProviderError, match="does not match"):
        provider.verify_webhook(payload=tampered, signature=signature, secret=SECRET)


def test_verification_is_over_the_raw_bytes() -> None:
    """Re-serialising parsed JSON reorders keys and changes whitespace, and the
    signature stops matching. The raw body is what must be signed."""
    provider = MockPaymentProvider()
    payload = b'{"id":"evt_1","type":"payment.succeeded","data":{"amount_cents":100}}'
    signature = provider.sign(payload, SECRET)

    reserialised = json.dumps(json.loads(payload)).encode()
    assert reserialised != payload
    with pytest.raises(PaymentProviderError):
        provider.verify_webhook(payload=reserialised, signature=signature, secret=SECRET)


def test_a_non_json_body_is_rejected() -> None:
    provider = MockPaymentProvider()
    payload = b"not json at all"
    with pytest.raises(PaymentProviderError, match="not JSON"):
        provider.verify_webhook(
            payload=payload, signature=provider.sign(payload, SECRET), secret=SECRET
        )


def test_a_body_without_id_or_type_is_rejected() -> None:
    provider = MockPaymentProvider()
    payload = json.dumps({"data": {}}).encode()
    with pytest.raises(PaymentProviderError, match="'id' and 'type'"):
        provider.verify_webhook(
            payload=payload, signature=provider.sign(payload, SECRET), secret=SECRET
        )
