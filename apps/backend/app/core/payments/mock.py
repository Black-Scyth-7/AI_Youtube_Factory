"""Deterministic mock payment provider.

Settles every charge, so the billing path runs end to end with no account and
no network. Ids are derived from the request rather than random, so a replayed
charge produces the same ``provider_payment_id`` and the idempotency in
``PaymentService.record_payment`` is genuinely exercised instead of being
accidentally satisfied by fresh ids.

Declines are reachable on demand — a reference containing ``decline`` is
refused — because the interesting billing code is the failure path, and a mock
that only ever succeeds tests half of it.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Final

from app.core.payments.interfaces import (
    ChargeResult,
    ChargeStatus,
    PaymentProviderError,
    RefundResult,
    WebhookEvent,
)

#: Substrings in a charge reference that force an outcome, for tests and demos.
DECLINE_MARKER: Final = "decline"
ACTION_MARKER: Final = "requires-action"


def _stable_id(prefix: str, *parts: object) -> str:
    """A deterministic id derived from the request."""
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return f"{prefix}_{digest[:24]}"


class MockPaymentProvider:
    """An in-process payment processor."""

    slug = "mock"

    async def charge(
        self,
        *,
        amount_cents: int,
        currency: str,
        reference: str,
        customer_reference: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> ChargeResult:
        if amount_cents <= 0:
            raise PaymentProviderError("Charge amount must be positive.")

        payment_id = _stable_id("mockpay", reference, amount_cents, currency)
        lowered = reference.lower()

        if DECLINE_MARKER in lowered:
            return ChargeResult(
                status=ChargeStatus.DECLINED,
                provider_payment_id=payment_id,
                amount_cents=amount_cents,
                currency=currency,
                decline_reason="card_declined",
            )
        if ACTION_MARKER in lowered:
            return ChargeResult(
                status=ChargeStatus.REQUIRES_ACTION,
                provider_payment_id=payment_id,
                amount_cents=amount_cents,
                currency=currency,
                action_url=f"https://payments.invalid/confirm/{payment_id}",
            )
        return ChargeResult(
            status=ChargeStatus.SUCCEEDED,
            provider_payment_id=payment_id,
            amount_cents=amount_cents,
            currency=currency,
            raw={"reference": reference, "customer": customer_reference},
        )

    async def refund(
        self, *, provider_payment_id: str, amount_cents: int
    ) -> RefundResult:
        if amount_cents <= 0:
            raise PaymentProviderError("Refund amount must be positive.")
        return RefundResult(
            provider_refund_id=_stable_id("mockref", provider_payment_id, amount_cents),
            amount_cents=amount_cents,
        )

    def verify_webhook(
        self, *, payload: bytes, signature: str | None, secret: str
    ) -> WebhookEvent:
        """Verify an HMAC-SHA256 signature over the raw body.

        The real providers differ in detail but not in shape, and the property
        that matters is the same: the signature is computed over the *raw*
        bytes. Re-serialising parsed JSON changes key order and whitespace, and
        the signature stops matching.
        """
        if not secret:
            raise PaymentProviderError(
                "No webhook secret is configured; refusing to accept callbacks."
            )
        if not signature:
            raise PaymentProviderError("Missing webhook signature.")

        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature.strip()):
            raise PaymentProviderError("Webhook signature does not match.")

        try:
            body: dict[str, Any] = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise PaymentProviderError(f"Webhook body is not JSON: {exc}") from exc

        event_id = body.get("id")
        event_type = body.get("type")
        if not isinstance(event_id, str) or not isinstance(event_type, str):
            raise PaymentProviderError("Webhook body needs string 'id' and 'type'.")

        raw_data = body.get("data")
        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
        amount = data.get("amount_cents")
        return WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            provider_payment_id=data.get("provider_payment_id"),
            amount_cents=amount if isinstance(amount, int) else None,
            payload=body,
        )

    @staticmethod
    def sign(payload: bytes, secret: str) -> str:
        """Produce a valid signature. For tests and local callbacks."""
        return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
