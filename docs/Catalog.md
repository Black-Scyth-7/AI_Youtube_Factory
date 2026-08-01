# Catalog domain

The Phase 06 breadth on top of the Phase 03 scaffolding: billing, notifications
and background jobs. Each area follows the same shape as the rest of the
codebase — model, repository, service — with business rules only in services.

## Billing

### Money

Amounts are **integer minor units** (cents), never floats. Binary floating point
cannot represent decimal currency exactly, and rounding drift in a billing
system is a bug you find in an audit. Genuinely fractional values — per-unit
overage rates — use `Numeric`, matching the LLM cost columns.

Rounding happens once, where a fractional usage total becomes a charge, with
`ROUND_HALF_UP` so a half-cent is never quietly lost.

### Plans and subscriptions

A `Plan` carries a price, an interval, optional trial days, and two JSON maps:

| Field           | Meaning                                                           |
| --------------- | ----------------------------------------------------------------- |
| `quotas`        | metric → allowance per period. A metric absent here is unlimited. |
| `overage_rates` | metric → cents per unit charged beyond the quota                  |

`SubscriptionService.subscribe` starts a trial when the plan offers one, and
refuses a second active subscription for the same organization. Cancelling
defaults to end-of-period, which keeps access until the period closes; passing
`at_period_end=False` revokes immediately.

Periods advance in fixed 30/365-day steps rather than calendar months, so every
period is the same length and usage rates stay comparable.

### Usage and invoicing

`UsageService.record` writes a `UsageRecord` per metered event.
`quota_remaining` returns `None` for "unlimited or no plan" — distinct from
`0`, which means the allowance is spent.

`InvoiceService.close_period` builds an invoice from the plan fee plus any
overage, then stamps every usage row it consumed with `invoiced_at`. That stamp
is what makes closing a period twice safe: the second call finds no uninvoiced
usage and charges only the plan fee.

### Payments

`record_payment` is idempotent on `provider_payment_id`. Payment providers retry
webhooks, and without this a retry would credit the invoice twice — the second
call returns the original payment instead. The column is unique, so the database
enforces it too.

Refunds reduce the invoice's paid amount and reopen it if the balance is no
longer covered.

## Notifications

`NotificationService.notify` returns `None` when the user has opted out of that
category on that channel, rather than creating a notification nobody wants.
Preferences default to enabled, so only explicit opt-outs suppress.

## Webhooks

Secrets follow the API-key pattern: `create` returns the raw secret **once** and
stores only its SHA-256 hash. Sign a payload with `sign_payload(secret, body)`
and the receiver verifies the HMAC-SHA256 hex digest.

`enqueue_event` fans an event out to every active webhook subscribed to it —
either by exact event type or `"*"`.

Delivery failures back off on a fixed schedule and then stop:

```python
RETRY_BACKOFF_SECONDS = (60, 300, 1800, 7200)
```

The tuple's length also caps the attempts, so a permanently broken endpoint is
marked `exhausted` instead of being retried forever. A success resets the
webhook's consecutive failure counter. Response bodies are truncated on write so
a verbose endpoint cannot fill the database.

## Jobs

`QueueJob` is the durable record of background work, deliberately separate from
the broker that carries it (Celery/RabbitMQ). A row here survives a broker
restart and is what the UI and retry logic read; `external_id` correlates it
with the Celery task.

State transitions are guarded: a job that already succeeded or was cancelled
cannot start again, a succeeded job cannot be cancelled, and `retry` only works
while `attempts < max_attempts`.

`RenderJobService.submit` creates both the render record and the queue job that
performs it. Completion **and failure** both publish `RenderFinished` — the
`success` flag distinguishes them, because subscribers need to know a render
ended either way, not only when it worked.

## Schema

Migration `0005_catalog` adds twelve tables:

```
plan  subscription  invoice  payment  usage_record  cost_record
notification  notification_preference  webhook  webhook_delivery
queue_job  render_job
```

Verified against PostgreSQL 17: `alembic upgrade head` creates all twelve, and
`downgrade 0004_agent` removes them.
