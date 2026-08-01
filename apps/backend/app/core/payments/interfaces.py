"""Payment provider contract.

Same shape as the LLM, storage, and pipeline abstractions: a Protocol with a
deterministic mock, so billing is exercised end to end without a Stripe account
and CI needs no secret.

Money is always integer minor units (cents). A float dollar amount cannot
represent 0.1 exactly, and rounding it repeatedly is how invoices stop adding
up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class PaymentProviderError(Exception):
    """A provider rejected an operation.

    Distinct from a *declined* charge, which is an ordinary outcome carried on
    :class:`ChargeResult` — a decline is the provider working correctly.
    """


class ChargeStatus(StrEnum):
    """Outcome of a charge attempt."""

    SUCCEEDED = "succeeded"
    #: The provider needs another step (3-D Secure, redirect) before settling.
    REQUIRES_ACTION = "requires_action"
    DECLINED = "declined"


@dataclass(frozen=True, slots=True)
class ChargeResult:
    """What the provider did with a charge request."""

    status: ChargeStatus
    #: Provider-side identifier. The unique key that makes replay idempotent.
    provider_payment_id: str
    amount_cents: int
    currency: str
    #: Set when the status is DECLINED.
    decline_reason: str | None = None
    #: Set when the status is REQUIRES_ACTION.
    action_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status is ChargeStatus.SUCCEEDED


@dataclass(frozen=True, slots=True)
class RefundResult:
    """What the provider did with a refund request."""

    provider_refund_id: str
    amount_cents: int
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WebhookEvent:
    """A verified provider callback.

    ``event_id`` is the provider's own id for the event and is what makes
    handling idempotent: providers retry until they get a 2xx, so the same
    event arrives more than once by design.
    """

    event_id: str
    event_type: str
    provider_payment_id: str | None
    amount_cents: int | None
    payload: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class PaymentProvider(Protocol):
    """What billing needs from a payment processor."""

    #: Registry slug, also written to ``Payment.provider``.
    slug: str

    async def charge(
        self,
        *,
        amount_cents: int,
        currency: str,
        reference: str,
        customer_reference: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> ChargeResult:
        """Attempt to collect ``amount_cents``.

        ``reference`` is this system's id for the thing being paid (an invoice
        id). Providers echo it back on webhooks, and passing it makes a
        callback resolvable without a lookup table.
        """
        ...

    async def refund(
        self, *, provider_payment_id: str, amount_cents: int
    ) -> RefundResult:
        """Return ``amount_cents`` of a settled charge."""
        ...

    def verify_webhook(
        self, *, payload: bytes, signature: str | None, secret: str
    ) -> WebhookEvent:
        """Authenticate and parse a callback.

        Raises:
            PaymentProviderError: If the signature is missing or does not match.
                An unverified callback is an unauthenticated request to move
                money and must never be processed.
        """
        ...
