"""Billing routes: plans, subscriptions, usage, invoices, and payments.

Everything except the public plan list and the provider webhook is scoped to an
organization and permission-checked. Money is only ever exchanged as integer
minor units.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, Request, Response, status

from app.core.payments import PaymentProviderError
from app.dependencies.auth import DbSession, require_permission
from app.exceptions.base import NotFoundError, UnauthorizedError
from app.models.user import User
from app.repositories.billing import PlanRepository, SubscriptionRepository
from app.schemas.billing import (
    CancelSubscriptionRequest,
    InvoiceResponse,
    PayInvoiceRequest,
    PayInvoiceResponse,
    PaymentResponse,
    PlanResponse,
    SubscribeRequest,
    SubscriptionResponse,
    UsageQuotaResponse,
    UsageSummaryResponse,
)
from app.services.billing import (
    InvoiceService,
    PlanService,
    SubscriptionService,
    UsageService,
)
from app.services.payment_gateway import PaymentGatewayService

router = APIRouter(prefix="/billing", tags=["billing"])


# -- Plans --------------------------------------------------------------------
@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(session: DbSession) -> list[PlanResponse]:
    """List purchasable plans.

    Unauthenticated: a pricing page needs this before anyone has an account.
    Only plans marked public are returned, so private and legacy pricing stays
    out of the catalogue.
    """
    plans = await PlanService(session).list_public()
    return [PlanResponse.model_validate(p) for p in plans]


# -- Subscription -------------------------------------------------------------
@router.get(
    "/organizations/{organization_id}/subscription",
    response_model=SubscriptionResponse | None,
)
async def get_subscription(
    organization_id: uuid.UUID,
    session: DbSession,
    _: User = Depends(require_permission("billing.read")),
) -> SubscriptionResponse | None:
    """The organization's active subscription, or null if it has none."""
    subscription = await SubscriptionService(session).get_active(organization_id)
    return SubscriptionResponse.model_validate(subscription) if subscription else None


@router.post(
    "/organizations/{organization_id}/subscription",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def subscribe(
    organization_id: uuid.UUID,
    body: SubscribeRequest,
    session: DbSession,
    _: User = Depends(require_permission("billing.manage")),
) -> SubscriptionResponse:
    """Subscribe the organization to a plan, replacing any active subscription."""
    subscription = await SubscriptionService(session).subscribe(
        organization_id, body.plan_code
    )
    return SubscriptionResponse.model_validate(subscription)


@router.post(
    "/organizations/{organization_id}/subscription/cancel",
    response_model=SubscriptionResponse,
)
async def cancel_subscription(
    organization_id: uuid.UUID,
    body: CancelSubscriptionRequest,
    session: DbSession,
    _: User = Depends(require_permission("billing.manage")),
) -> SubscriptionResponse:
    """Cancel the active subscription, at period end by default."""
    service = SubscriptionService(session)
    # The service cancels by subscription id; the caller only knows its
    # organization, so resolve the active one here. Passing the organization id
    # straight through looks right and always 404s.
    active = await service.get_active(organization_id)
    if active is None:
        raise NotFoundError("This organization has no active subscription.")

    subscription = await service.cancel(active.id, at_period_end=body.at_period_end)
    return SubscriptionResponse.model_validate(subscription)


# -- Usage --------------------------------------------------------------------
@router.get("/organizations/{organization_id}/usage", response_model=UsageSummaryResponse)
async def get_usage(
    organization_id: uuid.UUID,
    session: DbSession,
    _: User = Depends(require_permission("billing.read")),
) -> UsageSummaryResponse:
    """Consumption against the plan's allowances for the current period.

    Metrics the plan does not cap are reported with a null limit rather than
    omitted: "unlimited" and "not measured" look identical otherwise.
    """
    usage = UsageService(session)
    subscription = await SubscriptionRepository(session).get_active_for_organization(
        organization_id
    )
    if subscription is None:
        return UsageSummaryResponse(organization_id=organization_id, metrics=[])

    plan = await PlanRepository(session).get(subscription.plan_id)
    quotas: dict[str, int] = dict(plan.quotas) if plan else {}

    metrics: list[UsageQuotaResponse] = []
    for metric, limit in sorted(quotas.items()):
        used = await usage.repo.total_for_metric(
            organization_id, metric, subscription.current_period_start.date()
        )
        used_decimal = Decimal(str(used))
        remaining = int(Decimal(str(limit)) - used_decimal)
        metrics.append(
            UsageQuotaResponse(
                metric=metric,
                used=float(used_decimal),
                limit=limit,
                remaining=max(remaining, 0),
                exceeded=remaining < 0,
            )
        )

    return UsageSummaryResponse(
        organization_id=organization_id,
        period_start=subscription.current_period_start,
        period_end=subscription.current_period_end,
        metrics=metrics,
    )


# -- Invoices -----------------------------------------------------------------
@router.get(
    "/organizations/{organization_id}/invoices", response_model=list[InvoiceResponse]
)
async def list_invoices(
    organization_id: uuid.UUID,
    session: DbSession,
    _: User = Depends(require_permission("billing.read")),
) -> list[InvoiceResponse]:
    """Invoices for the organization, most recent first."""
    invoices = await InvoiceService(session).list_for_organization(organization_id)
    return [InvoiceResponse.model_validate(i) for i in invoices]


@router.post(
    "/organizations/{organization_id}/invoices/{invoice_id}/pay",
    response_model=PayInvoiceResponse,
)
async def pay_invoice(
    organization_id: uuid.UUID,
    invoice_id: uuid.UUID,
    body: PayInvoiceRequest,
    session: DbSession,
    _: User = Depends(require_permission("billing.manage")),
) -> PayInvoiceResponse:
    """Collect an invoice through the configured payment provider.

    A decline comes back as 200 with ``status="declined"``. The request was
    handled correctly; the card was not accepted, and the caller needs the
    reason rather than an error to retry against.
    """
    outcome = await PaymentGatewayService(session).charge_invoice(
        invoice_id,
        provider_slug=body.provider,
        customer_reference=body.customer_reference,
    )
    return PayInvoiceResponse(
        status=outcome.status.value,
        invoice_id=outcome.invoice.id,
        amount_cents=outcome.amount_cents,
        payment=(
            PaymentResponse.model_validate(outcome.payment) if outcome.payment else None
        ),
        decline_reason=outcome.decline_reason,
        action_url=outcome.action_url,
    )


@router.post(
    "/organizations/{organization_id}/payments/{payment_id}/refund",
    response_model=PaymentResponse,
)
async def refund_payment(
    organization_id: uuid.UUID,
    payment_id: uuid.UUID,
    session: DbSession,
    amount_cents: int | None = None,
    _: User = Depends(require_permission("billing.manage")),
) -> PaymentResponse:
    """Refund a settled payment, in full unless an amount is given."""
    payment = await PaymentGatewayService(session).refund_payment(
        payment_id, amount_cents
    )
    return PaymentResponse.model_validate(payment)


# -- Provider callbacks -------------------------------------------------------
@router.post("/webhooks/{provider_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def payment_webhook(
    provider_slug: str,
    request: Request,
    session: DbSession,
    response: Response,
    signature: str | None = Header(default=None, alias="X-Payment-Signature"),
) -> None:
    """Apply a verified provider callback.

    Unauthenticated by design — the provider has no session — but *verified*:
    the signature is checked over the raw request body before anything is read
    out of it. A bad signature is 401.

    A replayed event is a no-op and still returns 204. Providers retry until
    they get a 2xx, so answering an error to an event already handled is how a
    webhook queue backs up.
    """
    payload = await request.body()
    try:
        await PaymentGatewayService(session).handle_webhook(
            payload=payload, signature=signature, provider_slug=provider_slug
        )
    except PaymentProviderError as exc:
        raise UnauthorizedError(f"Webhook rejected: {exc}") from exc


__all__ = ["router"]
