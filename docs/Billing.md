# Billing

Plans, subscriptions, metered usage, invoices, and payments. The domain models
and services arrived in Phase 06; Phase 10 adds the payment provider
abstraction, the HTTP API, and the console page.

## Money is integer minor units

Every amount in the database, the API, and the provider contract is an integer
number of cents, named `*_cents`. It is divided exactly once, when rendered
(`formatMoney` in `lib/billing-api.ts`).

This is not fussiness. `0.1` has no exact binary representation, so a float
total drifts from the sum of its lines, and the drift compounds every time a
figure is stored and re-read. An invoice that disagrees with itself by a cent is
a support ticket and, at scale, an audit finding.

## Layers

```
routes/billing.py        HTTP, permissions, schemas
services/payment_gateway  charge / refund / apply callbacks
services/billing.py       plans, subscriptions, usage, invoices, payments
core/payments/            provider Protocol + deterministic mock
```

The gateway is deliberately separate from `services/billing.py`: the billing
rules are testable with no provider at all, and a provider can be added without
touching them.

## Providers

`PaymentProvider` is a Protocol with three operations — `charge`, `refund`, and
`verify_webhook` — and a registry keyed by slug, exactly like the LLM, storage,
and pipeline abstractions.

`mock` is always registered and settles in process, so the whole billing path
runs offline and CI needs no account. Its ids are derived from the request
rather than random, which matters: idempotency downstream keys off
`provider_payment_id`, and random ids would make the tests pass without the
guarantee ever holding.

Outcomes are forced by the charge reference, so the failure paths are reachable:

| Reference contains  | Outcome                          |
| ------------------- | -------------------------------- |
| `decline`           | `declined`, reason `card_declined` |
| `requires-action`   | `requires_action` with a URL     |
| anything else       | `succeeded`                      |

Adding a real provider:

```python
from app.core.payments import register_provider

register_provider("stripe", StripeProvider)
```

```bash
PAYMENT_PROVIDER=stripe
PAYMENT_WEBHOOK_SECRET=whsec_...
```

## A decline is not an error

`POST /billing/.../invoices/{id}/pay` answers **200** with
`status="declined"` when the card is refused. The request was handled correctly;
the caller needs the reason, not an exception to retry against a card that will
keep failing. Only a *broken* provider raises.

```json
{
  "status": "declined",
  "invoice_id": "…",
  "amount_cents": 5000,
  "payment": null,
  "decline_reason": "card_declined"
}
```

`requires_action` behaves the same way and carries `action_url` for 3-D Secure
or a redirect. No payment is recorded in either case.

## Idempotency

Providers retry until they get a 2xx, so **the same charge and the same callback
arrive more than once by design**. Two mechanisms handle it:

- `Payment.provider_payment_id` is unique, and `record_payment` returns the
  existing row rather than charging twice.
- `charge_invoice` computes the *outstanding* balance, so a partly paid invoice
  is never charged its full total again, and a settled one is refused before the
  provider is called at all.

An already-handled webhook is a no-op that still answers 204. Returning an error
for an event that was processed is how a provider's retry queue backs up.

## Webhooks

```
POST /api/v1/billing/webhooks/{provider_slug}
X-Payment-Signature: <hex hmac-sha256 of the raw body>
```

Unauthenticated by design — the provider has no session — but **verified**: the
signature is checked over the raw request body before anything is read out of
it. A callback moves money, so an unverified one is an unauthenticated request
to do so, and a bad signature is 401.

Verification is over the *raw bytes*. Re-serialising parsed JSON reorders keys
and changes whitespace, and the signature stops matching — there is a test for
exactly that. An empty `PAYMENT_WEBHOOK_SECRET` fails closed rather than
verifying everything.

## Quotas

`Plan.quotas` maps a metric to its allowance per period; a metric absent from
the map is unlimited. `Plan.overage_rates` prices each unit beyond the
allowance, and `InvoiceService.close_period` adds the overage to the plan fee.

`GET /billing/organizations/{id}/usage` reports every capped metric, including
ones at zero. A metric the plan does not cap is returned with a `null` limit
rather than omitted — "unlimited" and "not measured" are indistinguishable
otherwise.

## Permissions

| Endpoint                          | Permission       |
| --------------------------------- | ---------------- |
| `GET /billing/plans`              | none (public)    |
| `GET …/subscription`, `…/usage`, `…/invoices` | `billing.read`   |
| `POST …/subscription`, `…/cancel`, `…/pay`, `…/refund` | `billing.manage` |
| `POST /billing/webhooks/{slug}`   | signature only   |

`billing.read` is granted to owner, admin, and manager; `billing.manage` only to
the owner. Seeing the bill is not the same as being able to change the plan — a
manager spending the quota needs to know how much is left.

The plan list is public because a pricing page needs it before anyone has an
account. Only plans marked `is_public` are returned, so private and legacy
pricing stays out of the catalogue.

## Console

`/dashboard/billing` shows the current plan, consumption against each quota,
invoice history with a pay action, and the plan catalogue.
