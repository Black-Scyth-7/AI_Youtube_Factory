"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, CardContent, CardHeader, CardTitle, Input } from "@ayf/ui";

import { ApiRequestError } from "@/lib/auth-api";
import { useAuthStore } from "@/lib/auth-store";
import {
  type Invoice,
  type Plan,
  type Subscription,
  type UsageSummary,
  billingApi,
  formatMoney,
} from "@/lib/billing-api";

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleDateString() : "—";
}

function statusVariant(
  status: string,
): "success" | "secondary" | "destructive" {
  if (status === "paid" || status === "active" || status === "trialing") {
    return "success";
  }
  if (status === "void" || status === "past_due" || status === "cancelled") {
    return "destructive";
  }
  return "secondary";
}

/**
 * Billing console: the current plan, consumption against its quotas, and the
 * invoice history with a pay action.
 *
 * Amounts arrive as integer minor units and are divided only when rendered —
 * see `formatMoney`. Doing arithmetic on the formatted value is what makes a
 * total disagree with the sum of its lines.
 */
export default function BillingPage() {
  const token = useAuthStore((s) => s.accessToken);

  const [orgId, setOrgId] = useState("");
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  async function load() {
    if (!token || !orgId.trim()) {
      toast.error("An organization ID is required.");
      return;
    }
    setBusy(true);
    try {
      const id = orgId.trim();
      const [p, s, u, i] = await Promise.all([
        billingApi.plans(),
        billingApi.subscription(id, token),
        billingApi.usage(id, token),
        billingApi.invoices(id, token),
      ]);
      setPlans(p);
      setSubscription(s);
      setUsage(u);
      setInvoices(i);
      setLoaded(true);
    } catch (err) {
      toast.error(
        err instanceof ApiRequestError ? err.message : "Failed to load billing.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function subscribe(planCode: string) {
    if (!token) return;
    setBusy(true);
    try {
      setSubscription(await billingApi.subscribe(orgId.trim(), planCode, token));
      toast.success(`Subscribed to ${planCode}.`);
      setUsage(await billingApi.usage(orgId.trim(), token));
    } catch (err) {
      toast.error(err instanceof ApiRequestError ? err.message : "Subscribe failed.");
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!token) return;
    setBusy(true);
    try {
      setSubscription(await billingApi.cancel(orgId.trim(), true, token));
      toast.success("Cancels at the end of the current period.");
    } catch (err) {
      toast.error(err instanceof ApiRequestError ? err.message : "Cancel failed.");
    } finally {
      setBusy(false);
    }
  }

  async function pay(invoice: Invoice) {
    if (!token) return;
    setBusy(true);
    try {
      const result = await billingApi.payInvoice(orgId.trim(), invoice.id, token);
      // A decline is a successful request with an unsuccessful outcome. It
      // needs the reason surfaced, not an error toast that invites a retry
      // against a card that will keep failing.
      if (result.status === "succeeded") {
        toast.success(`Paid ${formatMoney(result.amount_cents, invoice.currency)}.`);
      } else if (result.status === "requires_action") {
        toast.warning("This payment needs confirmation from the cardholder.");
      } else {
        toast.error(`Declined: ${result.decline_reason ?? "unknown reason"}`);
      }
      setInvoices(await billingApi.invoices(orgId.trim(), token));
    } catch (err) {
      toast.error(err instanceof ApiRequestError ? err.message : "Payment failed.");
    } finally {
      setBusy(false);
    }
  }

  const currentPlan = plans.find((p) => p.id === subscription?.plan_id);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Billing</h1>
        {subscription && (
          <Badge variant={statusVariant(subscription.status)}>
            {subscription.status}
          </Badge>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Organization</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-64">
            <label className="mb-1 block text-sm text-muted-foreground" htmlFor="org">
              Organization ID
            </label>
            <Input
              id="org"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
            />
          </div>
          <Button onClick={load} disabled={busy}>
            {busy ? "Loading…" : "Load"}
          </Button>
        </CardContent>
      </Card>

      {loaded && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Current plan</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {subscription ? (
                <>
                  <p className="text-lg font-semibold">
                    {currentPlan?.name ?? "Unknown plan"}
                    {currentPlan && (
                      <span className="ml-2 text-sm font-normal text-muted-foreground">
                        {formatMoney(currentPlan.price_cents, currentPlan.currency)} /{" "}
                        {currentPlan.interval}
                      </span>
                    )}
                  </p>
                  <p className="text-muted-foreground">
                    Period {formatDate(subscription.current_period_start)} –{" "}
                    {formatDate(subscription.current_period_end)}
                  </p>
                  {subscription.trial_ends_at && (
                    <p className="text-muted-foreground">
                      Trial ends {formatDate(subscription.trial_ends_at)}
                    </p>
                  )}
                  {subscription.cancel_at_period_end ? (
                    <p className="text-destructive">
                      Cancels at the end of the current period.
                    </p>
                  ) : (
                    <Button variant="outline" onClick={cancel} disabled={busy}>
                      Cancel subscription
                    </Button>
                  )}
                </>
              ) : (
                <p className="text-muted-foreground">
                  This organization has no active subscription.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Usage this period</CardTitle>
            </CardHeader>
            <CardContent>
              {usage && usage.metrics.length > 0 ? (
                <div className="space-y-3">
                  {usage.metrics.map((m) => {
                    const pct =
                      m.limit && m.limit > 0
                        ? Math.min((m.used / m.limit) * 100, 100)
                        : 0;
                    return (
                      <div key={m.metric} className="space-y-1">
                        <div className="flex justify-between text-sm">
                          <span className="font-medium">{m.metric}</span>
                          <span
                            className={
                              m.exceeded ? "text-destructive" : "text-muted-foreground"
                            }
                          >
                            {m.used.toLocaleString()} /{" "}
                            {m.limit === null ? "unlimited" : m.limit.toLocaleString()}
                          </span>
                        </div>
                        <div className="h-2 w-full overflow-hidden rounded bg-muted">
                          <div
                            className={
                              m.exceeded ? "h-full bg-destructive" : "h-full bg-primary"
                            }
                            style={{ width: `${m.exceeded ? 100 : pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Nothing metered yet this period.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Invoices</CardTitle>
            </CardHeader>
            <CardContent>
              {invoices.length === 0 ? (
                <p className="text-sm text-muted-foreground">No invoices yet.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-left text-muted-foreground">
                      <tr>
                        <th className="py-2 pr-4 font-medium">Number</th>
                        <th className="py-2 pr-4 font-medium">Period</th>
                        <th className="py-2 pr-4 font-medium">Total</th>
                        <th className="py-2 pr-4 font-medium">Due</th>
                        <th className="py-2 pr-4 font-medium">Status</th>
                        <th className="py-2 font-medium" />
                      </tr>
                    </thead>
                    <tbody>
                      {invoices.map((inv) => {
                        const due = Math.max(
                          inv.total_cents - inv.amount_paid_cents,
                          0,
                        );
                        return (
                          <tr key={inv.id} className="border-t">
                            <td className="py-2 pr-4 font-mono">{inv.number}</td>
                            <td className="py-2 pr-4">
                              {formatDate(inv.period_start)} –{" "}
                              {formatDate(inv.period_end)}
                            </td>
                            <td className="py-2 pr-4">
                              {formatMoney(inv.total_cents, inv.currency)}
                            </td>
                            <td className="py-2 pr-4">
                              {formatMoney(due, inv.currency)}
                            </td>
                            <td className="py-2 pr-4">
                              <Badge variant={statusVariant(inv.status)}>
                                {inv.status}
                              </Badge>
                            </td>
                            <td className="py-2">
                              {due > 0 && inv.status !== "void" && (
                                <Button
                                  size="sm"
                                  onClick={() => pay(inv)}
                                  disabled={busy}
                                >
                                  Pay
                                </Button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Available plans</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {plans.map((plan) => (
                <div key={plan.id} className="rounded-lg border p-4">
                  <p className="font-semibold">{plan.name}</p>
                  <p className="text-2xl font-bold">
                    {formatMoney(plan.price_cents, plan.currency)}
                    <span className="text-sm font-normal text-muted-foreground">
                      {" "}
                      / {plan.interval}
                    </span>
                  </p>
                  {plan.trial_days > 0 && (
                    <p className="text-sm text-muted-foreground">
                      {plan.trial_days}-day trial
                    </p>
                  )}
                  <ul className="my-3 space-y-1 text-sm text-muted-foreground">
                    {plan.features.map((f) => (
                      <li key={f}>· {f}</li>
                    ))}
                  </ul>
                  <Button
                    className="w-full"
                    variant={plan.id === subscription?.plan_id ? "outline" : "primary"}
                    disabled={busy || plan.id === subscription?.plan_id}
                    onClick={() => subscribe(plan.code)}
                  >
                    {plan.id === subscription?.plan_id ? "Current plan" : "Choose"}
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
