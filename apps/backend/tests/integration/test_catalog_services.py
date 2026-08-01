"""Tests for the Phase 06 catalog services: billing, notifications, and jobs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.events import Event, EventBus, RenderFinished, set_event_bus
from app.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.models.billing import Plan
from app.models.domain_enums import (
    InvoiceStatus,
    JobStatus,
    NotificationChannel,
    PaymentStatus,
    SubscriptionStatus,
    UsageMetric,
    WebhookDeliveryStatus,
)
from app.security.tokens import hash_token
from app.services.billing import (
    CostService,
    InvoiceService,
    PaymentService,
    PlanService,
    SubscriptionService,
    UsageService,
)
from app.services.job import QueueJobService, RenderJobService
from app.services.notification import (
    RETRY_BACKOFF_SECONDS,
    NotificationService,
    WebhookService,
    sign_payload,
)
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


async def _make_plan(
    session: AsyncSession,
    *,
    code: str = "pro",
    price_cents: int = 5000,
    trial_days: int = 0,
    quotas: dict[str, object] | None = None,
    overage: dict[str, object] | None = None,
) -> Plan:
    plan = Plan(
        code=code,
        name=code.title(),
        price_cents=price_cents,
        trial_days=trial_days,
        quotas=quotas or {},
        overage_rates=overage or {},
    )
    session.add(plan)
    await session.flush()
    return plan


# -- Subscriptions ------------------------------------------------------------
async def test_subscribe_starts_a_trial_when_the_plan_offers_one(
    session: AsyncSession,
) -> None:
    await _make_plan(session, code="trial-plan", trial_days=14)
    sub = await SubscriptionService(session).subscribe(uuid.uuid4(), "trial-plan")

    assert sub.status == SubscriptionStatus.TRIALING.value
    assert sub.trial_ends_at is not None
    assert sub.current_period_end > sub.current_period_start


async def test_subscribe_is_active_immediately_without_a_trial(
    session: AsyncSession,
) -> None:
    await _make_plan(session, code="no-trial", trial_days=0)
    sub = await SubscriptionService(session).subscribe(uuid.uuid4(), "no-trial")

    assert sub.status == SubscriptionStatus.ACTIVE.value
    assert sub.trial_ends_at is None


async def test_subscribing_twice_is_rejected(session: AsyncSession) -> None:
    await _make_plan(session, code="dup-plan")
    org = uuid.uuid4()
    service = SubscriptionService(session)
    await service.subscribe(org, "dup-plan")

    with pytest.raises(ConflictError):
        await service.subscribe(org, "dup-plan")


async def test_subscribe_to_an_unknown_plan_raises(session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await SubscriptionService(session).subscribe(uuid.uuid4(), "does-not-exist")


async def test_cancel_at_period_end_keeps_access(session: AsyncSession) -> None:
    """Cancelling at period end must not revoke access immediately."""
    await _make_plan(session, code="keep-access")
    service = SubscriptionService(session)
    org = uuid.uuid4()
    sub = await service.subscribe(org, "keep-access")

    cancelled = await service.cancel(sub.id, at_period_end=True)
    assert cancelled.cancel_at_period_end is True
    assert cancelled.status == SubscriptionStatus.ACTIVE.value
    assert await service.get_active(org) is not None


async def test_cancel_immediately_revokes_access(session: AsyncSession) -> None:
    await _make_plan(session, code="revoke-now")
    service = SubscriptionService(session)
    org = uuid.uuid4()
    sub = await service.subscribe(org, "revoke-now")

    await service.cancel(sub.id, at_period_end=False)
    assert await service.get_active(org) is None


# -- Usage and quotas ---------------------------------------------------------
async def test_usage_counts_against_the_plan_quota(session: AsyncSession) -> None:
    await _make_plan(session, code="quota-plan", quotas={UsageMetric.PUBLISH.value: 10})
    org = uuid.uuid4()
    await SubscriptionService(session).subscribe(org, "quota-plan")
    usage = UsageService(session)

    assert await usage.quota_remaining(org, UsageMetric.PUBLISH.value) == Decimal("10")
    await usage.record(org, UsageMetric.PUBLISH.value, 4)
    assert await usage.quota_remaining(org, UsageMetric.PUBLISH.value) == Decimal("6")
    assert await usage.is_within_quota(org, UsageMetric.PUBLISH.value) is True


async def test_exhausted_quota_reports_not_within(session: AsyncSession) -> None:
    await _make_plan(session, code="small-quota", quotas={UsageMetric.PUBLISH.value: 2})
    org = uuid.uuid4()
    await SubscriptionService(session).subscribe(org, "small-quota")
    usage = UsageService(session)
    await usage.record(org, UsageMetric.PUBLISH.value, 2)

    assert await usage.is_within_quota(org, UsageMetric.PUBLISH.value) is False


async def test_a_metric_without_a_quota_is_unlimited(session: AsyncSession) -> None:
    await _make_plan(session, code="unlimited")
    org = uuid.uuid4()
    await SubscriptionService(session).subscribe(org, "unlimited")

    assert await UsageService(session).quota_remaining(org, "anything") is None
    assert await UsageService(session).is_within_quota(org, "anything") is True


async def test_negative_usage_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await UsageService(session).record(uuid.uuid4(), UsageMetric.PUBLISH.value, -1)


# -- Invoicing ----------------------------------------------------------------
async def test_invoice_charges_the_plan_fee(session: AsyncSession) -> None:
    await _make_plan(session, code="flat", price_cents=2500)
    org = uuid.uuid4()
    sub = await SubscriptionService(session).subscribe(org, "flat")

    invoice = await InvoiceService(session).close_period(sub.id)
    assert invoice.total_cents == 2500
    assert invoice.status == InvoiceStatus.OPEN.value
    assert len(invoice.line_items) == 1


async def test_invoice_adds_overage_beyond_the_quota(session: AsyncSession) -> None:
    await _make_plan(
        session,
        code="metered",
        price_cents=1000,
        quotas={UsageMetric.PUBLISH.value: 5},
        overage={UsageMetric.PUBLISH.value: 50},  # 50 cents per unit
    )
    org = uuid.uuid4()
    sub = await SubscriptionService(session).subscribe(org, "metered")
    await UsageService(session).record(org, UsageMetric.PUBLISH.value, 8)

    invoice = await InvoiceService(session).close_period(sub.id)
    # 3 units over quota at 50c = 150c, plus the 1000c plan fee.
    assert invoice.total_cents == 1150
    assert len(invoice.line_items) == 2


async def test_usage_within_quota_adds_no_overage(session: AsyncSession) -> None:
    await _make_plan(
        session,
        code="under",
        price_cents=1000,
        quotas={UsageMetric.PUBLISH.value: 10},
        overage={UsageMetric.PUBLISH.value: 50},
    )
    org = uuid.uuid4()
    sub = await SubscriptionService(session).subscribe(org, "under")
    await UsageService(session).record(org, UsageMetric.PUBLISH.value, 3)

    invoice = await InvoiceService(session).close_period(sub.id)
    assert invoice.total_cents == 1000


async def test_usage_is_billed_only_once(session: AsyncSession) -> None:
    """Closing a period twice must not charge the same usage again."""
    await _make_plan(
        session,
        code="once",
        price_cents=0,
        quotas={UsageMetric.PUBLISH.value: 0},
        overage={UsageMetric.PUBLISH.value: 100},
    )
    org = uuid.uuid4()
    sub = await SubscriptionService(session).subscribe(org, "once")
    await UsageService(session).record(org, UsageMetric.PUBLISH.value, 2)

    service = InvoiceService(session)
    first = await service.close_period(sub.id)
    second = await service.close_period(sub.id)

    assert first.total_cents == 200
    assert second.total_cents == 0  # nothing left to bill


async def test_overage_rounds_half_up(session: AsyncSession) -> None:
    """A half-cent must round up, not silently vanish."""
    await _make_plan(
        session,
        code="rounding",
        price_cents=0,
        quotas={UsageMetric.API_CALL.value: 0},
        overage={UsageMetric.API_CALL.value: 0.5},
    )
    org = uuid.uuid4()
    sub = await SubscriptionService(session).subscribe(org, "rounding")
    await UsageService(session).record(org, UsageMetric.API_CALL.value, 3)

    invoice = await InvoiceService(session).close_period(sub.id)
    assert invoice.total_cents == 2  # 3 * 0.5 = 1.5 -> 2


# -- Payments -----------------------------------------------------------------
async def test_full_payment_marks_the_invoice_paid(session: AsyncSession) -> None:
    await _make_plan(session, code="payme", price_cents=3000)
    org = uuid.uuid4()
    sub = await SubscriptionService(session).subscribe(org, "payme")
    invoice = await InvoiceService(session).close_period(sub.id)

    await PaymentService(session).record_payment(invoice.id, 3000)
    assert invoice.status == InvoiceStatus.PAID.value
    assert invoice.paid_at is not None
    assert invoice.amount_due_cents == 0


async def test_partial_payment_leaves_the_invoice_open(session: AsyncSession) -> None:
    await _make_plan(session, code="partial", price_cents=3000)
    org = uuid.uuid4()
    sub = await SubscriptionService(session).subscribe(org, "partial")
    invoice = await InvoiceService(session).close_period(sub.id)

    await PaymentService(session).record_payment(invoice.id, 1000)
    assert invoice.status == InvoiceStatus.OPEN.value
    assert invoice.amount_due_cents == 2000


async def test_replayed_provider_webhook_does_not_double_charge(
    session: AsyncSession,
) -> None:
    """Payment providers retry webhooks; the second must be a no-op."""
    await _make_plan(session, code="idem", price_cents=1000)
    org = uuid.uuid4()
    sub = await SubscriptionService(session).subscribe(org, "idem")
    invoice = await InvoiceService(session).close_period(sub.id)
    service = PaymentService(session)

    first = await service.record_payment(
        invoice.id, 1000, provider="stripe", provider_payment_id="pi_123"
    )
    second = await service.record_payment(
        invoice.id, 1000, provider="stripe", provider_payment_id="pi_123"
    )

    assert first.id == second.id
    assert invoice.amount_paid_cents == 1000


async def test_refund_reopens_the_invoice(session: AsyncSession) -> None:
    await _make_plan(session, code="refundable", price_cents=2000)
    org = uuid.uuid4()
    sub = await SubscriptionService(session).subscribe(org, "refundable")
    invoice = await InvoiceService(session).close_period(sub.id)
    service = PaymentService(session)
    payment = await service.record_payment(invoice.id, 2000)
    assert invoice.status == InvoiceStatus.PAID.value

    await service.refund(payment.id, 500)
    assert invoice.status == InvoiceStatus.OPEN.value
    assert invoice.paid_at is None
    assert invoice.amount_due_cents == 500


async def test_full_refund_marks_the_payment_refunded(session: AsyncSession) -> None:
    await _make_plan(session, code="fullrefund", price_cents=1000)
    org = uuid.uuid4()
    sub = await SubscriptionService(session).subscribe(org, "fullrefund")
    invoice = await InvoiceService(session).close_period(sub.id)
    service = PaymentService(session)
    payment = await service.record_payment(invoice.id, 1000)

    await service.refund(payment.id, 1000)
    assert payment.status == PaymentStatus.REFUNDED.value


async def test_over_refund_is_rejected(session: AsyncSession) -> None:
    await _make_plan(session, code="overrefund", price_cents=1000)
    org = uuid.uuid4()
    sub = await SubscriptionService(session).subscribe(org, "overrefund")
    invoice = await InvoiceService(session).close_period(sub.id)
    service = PaymentService(session)
    payment = await service.record_payment(invoice.id, 1000)

    with pytest.raises(ValidationError):
        await service.refund(payment.id, 1500)


async def test_non_positive_payment_is_rejected(session: AsyncSession) -> None:
    await _make_plan(session, code="zeropay", price_cents=100)
    org = uuid.uuid4()
    sub = await SubscriptionService(session).subscribe(org, "zeropay")
    invoice = await InvoiceService(session).close_period(sub.id)

    with pytest.raises(ValidationError):
        await PaymentService(session).record_payment(invoice.id, 0)


async def test_plan_service_lists_public_plans(session: AsyncSession) -> None:
    await _make_plan(session, code="visible", price_cents=100)
    plans = await PlanService(session).list_public()
    assert any(p.code == "visible" for p in plans)


async def test_negative_cost_is_rejected(session: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await CostService(session).record("llm", -1)


# -- Notifications ------------------------------------------------------------
async def test_notify_and_read(session: AsyncSession) -> None:
    service = NotificationService(session)
    user = uuid.uuid4()
    notification = await service.notify(user, "render", "Render finished")
    assert notification is not None
    assert await service.unread_count(user) == 1

    await service.mark_read(notification.id)
    assert notification.read_at is not None
    assert await service.unread_count(user) == 0


async def test_opting_out_suppresses_the_notification(session: AsyncSession) -> None:
    service = NotificationService(session)
    user = uuid.uuid4()
    await service.set_preference(
        user, "marketing", NotificationChannel.IN_APP.value, enabled=False
    )

    assert await service.notify(user, "marketing", "Sale!") is None
    assert await service.unread_count(user) == 0
    # An unrelated category is unaffected.
    assert await service.notify(user, "render", "Done") is not None


async def test_mark_all_read(session: AsyncSession) -> None:
    service = NotificationService(session)
    user = uuid.uuid4()
    for i in range(3):
        await service.notify(user, "render", f"Job {i}")

    assert await service.mark_all_read(user) == 3
    assert await service.unread_count(user) == 0


# -- Webhooks -----------------------------------------------------------------
async def test_webhook_secret_is_returned_once_and_stored_hashed(
    session: AsyncSession,
) -> None:
    webhook, secret = await WebhookService(session).create(
        uuid.uuid4(), "Prod", "https://example.com/hook", ["video.published"]
    )
    assert secret
    assert webhook.secret_hash == hash_token(secret)
    assert secret not in webhook.secret_hash


async def test_webhook_url_must_be_http(session: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await WebhookService(session).create(
            uuid.uuid4(), "Bad", "ftp://example.com", ["video.published"]
        )


async def test_webhook_needs_at_least_one_event(session: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await WebhookService(session).create(
            uuid.uuid4(), "Bad", "https://example.com", []
        )


async def test_events_go_only_to_subscribed_webhooks(session: AsyncSession) -> None:
    service = WebhookService(session)
    org = uuid.uuid4()
    await service.create(org, "Publishes", "https://a.example/h", ["video.published"])
    await service.create(org, "Renders", "https://b.example/h", ["render.finished"])
    await service.create(org, "Everything", "https://c.example/h", ["*"])

    deliveries = await service.enqueue_event(org, "video.published", {"id": "1"})
    assert len(deliveries) == 2  # the publisher and the wildcard


async def test_failed_delivery_backs_off_then_gives_up(session: AsyncSession) -> None:
    service = WebhookService(session)
    org = uuid.uuid4()
    await service.create(org, "Flaky", "https://flaky.example/h", ["*"])
    delivery = (await service.enqueue_event(org, "any.event", {}))[0]

    for _ in range(1, len(RETRY_BACKOFF_SECONDS)):
        await service.record_failure(delivery.id, error="boom")
        assert delivery.status == WebhookDeliveryStatus.FAILED.value
        assert delivery.next_retry_at is not None

    # The final attempt exhausts the schedule rather than retrying forever.
    await service.record_failure(delivery.id, error="boom")
    assert delivery.status == WebhookDeliveryStatus.EXHAUSTED.value
    assert delivery.next_retry_at is None


async def test_success_clears_the_failure_counter(session: AsyncSession) -> None:
    service = WebhookService(session)
    org = uuid.uuid4()
    webhook, _ = await service.create(org, "Hook", "https://ok.example/h", ["*"])
    delivery = (await service.enqueue_event(org, "any.event", {}))[0]

    await service.record_failure(delivery.id, error="transient")
    assert webhook.failure_count == 1

    await service.record_success(delivery.id, 200, "ok")
    assert delivery.status == WebhookDeliveryStatus.DELIVERED.value
    assert webhook.failure_count == 0
    assert webhook.last_success_at is not None


async def test_oversized_response_body_is_truncated(session: AsyncSession) -> None:
    service = WebhookService(session)
    org = uuid.uuid4()
    await service.create(org, "Chatty", "https://chatty.example/h", ["*"])
    delivery = (await service.enqueue_event(org, "any.event", {}))[0]

    await service.record_success(delivery.id, 200, "x" * 10_000)
    assert delivery.response_body is not None
    assert len(delivery.response_body) <= 2048


def test_signature_is_stable_and_secret_dependent() -> None:
    payload = '{"a":1}'
    assert sign_payload("s1", payload) == sign_payload("s1", payload)
    assert sign_payload("s1", payload) != sign_payload("s2", payload)


# -- Jobs ---------------------------------------------------------------------
async def test_queue_job_lifecycle(session: AsyncSession) -> None:
    service = QueueJobService(session)
    job = await service.enqueue("render.media", payload={"video_id": "x"})
    assert job.status == JobStatus.QUEUED.value

    await service.mark_running(job.id, external_id="celery-1")
    assert job.status == JobStatus.RUNNING.value
    assert job.attempts == 1
    assert job.external_id == "celery-1"

    await service.mark_succeeded(job.id, {"ok": True})
    assert job.status == JobStatus.SUCCEEDED.value
    assert job.result == {"ok": True}


async def test_failed_job_can_retry_until_attempts_run_out(
    session: AsyncSession,
) -> None:
    service = QueueJobService(session)
    job = await service.enqueue("flaky.task", max_attempts=2)

    await service.mark_running(job.id)
    await service.mark_failed(job.id, "boom")
    assert job.can_retry is True

    await service.retry(job.id)
    await service.mark_running(job.id)
    await service.mark_failed(job.id, "boom again")
    assert job.attempts == 2
    assert job.can_retry is False

    with pytest.raises(ConflictError):
        await service.retry(job.id)


async def test_a_finished_job_cannot_start_again(session: AsyncSession) -> None:
    service = QueueJobService(session)
    job = await service.enqueue("done.task")
    await service.mark_running(job.id)
    await service.mark_succeeded(job.id)

    with pytest.raises(ConflictError):
        await service.mark_running(job.id)


async def test_a_succeeded_job_cannot_be_cancelled(session: AsyncSession) -> None:
    service = QueueJobService(session)
    job = await service.enqueue("done.task")
    await service.mark_succeeded(job.id)

    with pytest.raises(ConflictError):
        await service.cancel(job.id)


async def test_enqueue_rejects_zero_attempts(session: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await QueueJobService(session).enqueue("bad.task", max_attempts=0)


async def test_scheduled_jobs_are_not_ready_yet(session: AsyncSession) -> None:
    service = QueueJobService(session)
    await service.enqueue(
        "later.task", scheduled_for=datetime.now(UTC) + timedelta(hours=1)
    )
    await service.enqueue("now.task")

    ready = await service.ready()
    names = {job.task_name for job in ready}
    assert "now.task" in names
    assert "later.task" not in names


# -- Render jobs --------------------------------------------------------------
@pytest.fixture()
def render_events() -> list[Event]:
    bus = EventBus()
    captured: list[Event] = []

    async def _record(event: Event) -> None:
        captured.append(event)

    bus.subscribe(RenderFinished, _record)
    set_event_bus(bus)
    return captured


async def test_render_submits_a_queue_job_and_completes(
    session: AsyncSession, render_events: list[Event]
) -> None:
    service = RenderJobService(session)
    video_id = uuid.uuid4()
    render = await service.submit(video_id)

    assert render.status == JobStatus.QUEUED.value
    assert render.queue_job_id is not None  # the work was actually queued

    await service.update_progress(render.id, 50)
    assert render.status == JobStatus.RUNNING.value

    await service.complete(render.id, output_key="renders/a.mp4", output_bytes=1024)
    assert render.status == JobStatus.SUCCEEDED.value
    assert render.progress == 100
    assert render.output_key == "renders/a.mp4"

    assert [type(e).__name__ for e in render_events] == ["RenderFinished"]
    assert render_events[0].success is True


async def test_a_failed_render_still_announces_that_it_finished(
    session: AsyncSession, render_events: list[Event]
) -> None:
    """Subscribers need to know the render ended, not only that it worked."""
    service = RenderJobService(session)
    render = await service.submit(uuid.uuid4())

    await service.fail(render.id, "encoder crashed")
    assert render.status == JobStatus.FAILED.value
    assert len(render_events) == 1
    assert render_events[0].success is False


async def test_progress_outside_the_range_is_rejected(session: AsyncSession) -> None:
    service = RenderJobService(session)
    render = await service.submit(uuid.uuid4())

    for bad in (-1, 101):
        with pytest.raises(ValidationError):
            await service.update_progress(render.id, bad)


async def test_operations_on_a_missing_render_raise(session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await RenderJobService(session).update_progress(uuid.uuid4(), 10)
