"""Payment providers.

A Protocol plus a deterministic mock, resolved through a registry — the same
shape as the LLM, storage, and pipeline abstractions, so billing runs offline.
"""

from __future__ import annotations

from app.core.payments.interfaces import (
    ChargeResult,
    ChargeStatus,
    PaymentProvider,
    PaymentProviderError,
    RefundResult,
    WebhookEvent,
)
from app.core.payments.mock import MockPaymentProvider
from app.core.payments.registry import (
    available_providers,
    get_provider,
    register_provider,
    reset_providers,
)

__all__ = [
    "ChargeResult",
    "ChargeStatus",
    "MockPaymentProvider",
    "PaymentProvider",
    "PaymentProviderError",
    "RefundResult",
    "WebhookEvent",
    "available_providers",
    "get_provider",
    "register_provider",
    "reset_providers",
]
