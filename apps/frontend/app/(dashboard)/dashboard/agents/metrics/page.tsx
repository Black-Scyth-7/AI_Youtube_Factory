"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@ayf/ui";

import { type MetricsReport, agentApi } from "@/lib/agent-api";
import { ApiRequestError } from "@/lib/auth-api";
import { useAuthStore } from "@/lib/auth-store";

/**
 * Agent metrics dashboard: aggregate runs, success rate, tokens, cost, latency,
 * and the live monitor snapshot for an organization.
 */
export default function AgentMetricsPage() {
  const token = useAuthStore((s) => s.accessToken);
  const [orgId, setOrgId] = useState("");
  const [report, setReport] = useState<MetricsReport | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!token || !orgId.trim()) {
      toast.error("An organization ID is required.");
      return;
    }
    setBusy(true);
    try {
      setReport(await agentApi.metrics(token, orgId.trim()));
    } catch (err) {
      toast.error(err instanceof ApiRequestError ? err.message : "Failed to load.");
    } finally {
      setBusy(false);
    }
  }

  const cards: { label: string; value: string }[] = report
    ? [
        { label: "Runs", value: report.runs.toLocaleString() },
        {
          label: "Success rate",
          value: `${(report.success_rate * 100).toFixed(0)}%`,
        },
        { label: "Running now", value: report.monitor.running.toLocaleString() },
        { label: "Total tokens", value: report.total_tokens.toLocaleString() },
        { label: "Total cost", value: `$${report.total_cost_usd.toFixed(4)}` },
        { label: "Avg latency", value: `${report.avg_latency_ms.toFixed(0)}ms` },
        { label: "Tool calls", value: report.monitor.tool_calls.toLocaleString() },
        {
          label: "Failed runs",
          value: report.monitor.runs_failed.toLocaleString(),
        },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Agent metrics</h1>
        <Badge variant="secondary">Monitoring</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Organization</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-2">
          <input
            className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm"
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            placeholder="organization uuid"
          />
          <Button onClick={() => void load()} disabled={busy}>
            {busy ? "Loading…" : "Load metrics"}
          </Button>
        </CardContent>
      </Card>

      {report && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map((c) => (
            <Card key={c.label}>
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {c.label}
                </CardTitle>
              </CardHeader>
              <CardContent className="text-2xl font-bold">{c.value}</CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
