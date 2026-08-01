import { API_BASE_PATH } from "@ayf/shared";

import { ApiRequestError } from "./auth-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// -- Response types (mirrors app/schemas/billing.py) ---------------------
// Money is always integer minor units. Never parse it into a float: 0.1 has no
// exact binary representation, and a total that is off by a cent is a support
// ticket.

export interface Plan {
  id: string;
  code: string;
  name: string;
  description: string | null;
  price_cents: number;
  currency: string;
  interval: string;
  trial_days: number;
  quotas: Record<string, number>;
  overage_rates: Record<string, number>;
  features: string[];
}

export interface Subscription {
  id: string;
  organization_id: string;
  plan_id: string;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  trial_ends_at: string | null;
  cancel_at_period_end: boolean;
  cancelled_at: string | null;
  external_reference: string | null;
}

export interface InvoiceLine {
  description: string;
  quantity: number;
  unit_price_cents: number;
  amount_cents: number;
}

export interface Invoice {
  id: string;
  organization_id: string;
  number: string;
  status: string;
  currency: string;
  subtotal_cents: number;
  tax_cents: number;
  total_cents: number;
  amount_paid_cents: number;
  period_start: string | null;
  period_end: string | null;
  due_at: string | null;
  paid_at: string | null;
  line_items: InvoiceLine[];
}

export interface Payment {
  id: string;
  invoice_id: string;
  status: string;
  amount_cents: number;
  currency: string;
  provider: string | null;
  refunded_cents: number;
  failure_reason: string | null;
  processed_at: string | null;
}

export interface PayInvoiceResult {
  status: "succeeded" | "declined" | "requires_action";
  invoice_id: string;
  amount_cents: number;
  payment: Payment | null;
  decline_reason: string | null;
  action_url: string | null;
}

export interface UsageQuota {
  metric: string;
  used: number;
  limit: number | null;
  remaining: number | null;
  exceeded: boolean;
}

export interface UsageSummary {
  organization_id: string;
  period_start: string | null;
  period_end: string | null;
  metrics: UsageQuota[];
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  accessToken?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("content-type", "application/json");
  if (accessToken) headers.set("authorization", `Bearer ${accessToken}`);

  const res = await fetch(`${API_URL}${API_BASE_PATH}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (res.status === 204) return undefined as T;

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error ?? {};
    throw new ApiRequestError(
      err.message ?? "Request failed",
      err.code ?? "error",
      res.status,
    );
  }
  return body as T;
}

/**
 * Format integer minor units for display.
 *
 * The division happens once, here, at the edge. Doing arithmetic on the result
 * is what makes totals drift.
 */
export function formatMoney(cents: number, currency = "USD"): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
  }).format(cents / 100);
}

/** Typed client for the /billing/* endpoints. */
export const billingApi = {
  plans: () => request<Plan[]>("/billing/plans"),

  subscription: (organizationId: string, token: string) =>
    request<Subscription | null>(
      `/billing/organizations/${organizationId}/subscription`,
      {},
      token,
    ),

  subscribe: (organizationId: string, planCode: string, token: string) =>
    request<Subscription>(
      `/billing/organizations/${organizationId}/subscription`,
      { method: "POST", body: JSON.stringify({ plan_code: planCode }) },
      token,
    ),

  cancel: (organizationId: string, atPeriodEnd: boolean, token: string) =>
    request<Subscription>(
      `/billing/organizations/${organizationId}/subscription/cancel`,
      { method: "POST", body: JSON.stringify({ at_period_end: atPeriodEnd }) },
      token,
    ),

  usage: (organizationId: string, token: string) =>
    request<UsageSummary>(
      `/billing/organizations/${organizationId}/usage`,
      {},
      token,
    ),

  invoices: (organizationId: string, token: string) =>
    request<Invoice[]>(
      `/billing/organizations/${organizationId}/invoices`,
      {},
      token,
    ),

  payInvoice: (organizationId: string, invoiceId: string, token: string) =>
    request<PayInvoiceResult>(
      `/billing/organizations/${organizationId}/invoices/${invoiceId}/pay`,
      { method: "POST", body: JSON.stringify({}) },
      token,
    ),
};
