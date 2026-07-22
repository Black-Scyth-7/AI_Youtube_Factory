"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@ayf/ui";

import { ApiRequestError } from "@/lib/auth-api";
import { useAuthStore } from "@/lib/auth-store";
import { type CostSummary, type UsageSummary, llmApi } from "@/lib/llm-api";

function isoDaysAgo(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

/**
 * Token-usage and cost dashboard. Queries the accounting rollups for an
 * organization over a date range and shows aggregate token counts, request
 * volume, and cost broken down by input/output.
 */
export default function UsageDashboardPage() {
  const token = useAuthStore((s) => s.accessToken);

  const [orgId, setOrgId] = useState("");
  const [start, setStart] = useState(isoDaysAgo(30));
  const [end, setEnd] = useState(isoDaysAgo(0));
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [cost, setCost] = useState<CostSummary | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!token || !orgId.trim()) {
      toast.error("An organization ID is required.");
      return;
    }
    setBusy(true);
    try {
      const [u, c] = await Promise.all([
        llmApi.usage(token, orgId.trim(), start, end),
        llmApi.costs(token, orgId.trim(), start, end),
      ]);
      setUsage(u);
      setCost(c);
    } catch (err) {
      toast.error(
        err instanceof ApiRequestError ? err.message : "Failed to load usage.",
      );
    } finally {
      setBusy(false);
    }
  }

  const stats: { label: string; value: string }[] = [
    {
      label: "Requests",
      value: usage ? usage.request_count.toLocaleString() : "—",
    },
    {
      label: "Input tokens",
      value: usage ? usage.input_tokens.toLocaleString() : "—",
    },
    {
      label: "Output tokens",
      value: usage ? usage.output_tokens.toLocaleString() : "—",
    },
    {
      label: "Total tokens",
      value: usage ? usage.total_tokens.toLocaleString() : "—",
    },
  ];

  const costs: { label: string; value: string }[] = [
    {
      label: "Input cost",
      value: cost ? `$${cost.input_cost_usd.toFixed(4)}` : "—",
    },
    {
      label: "Output cost",
      value: cost ? `$${cost.output_cost_usd.toFixed(4)}` : "—",
    },
    {
      label: "Total cost",
      value: cost ? `$${cost.total_cost_usd.toFixed(4)}` : "—",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Usage & cost</h1>
        <Badge variant="secondary">Accounting</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Query</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-4">
          <label className="space-y-1 text-sm sm:col-span-2">
            <span className="font-medium">Organization ID</span>
            <input
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              placeholder="organization uuid"
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="font-medium">Start</span>
            <input
              type="date"
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="font-medium">End</span>
            <input
              type="date"
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
          <div className="sm:col-span-4">
            <Button onClick={() => void load()} disabled={busy}>
              {busy ? "Loading…" : "Load report"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {s.label}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-bold">{s.value}</CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {costs.map((s) => (
          <Card key={s.label}>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {s.label}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-bold">{s.value}</CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
