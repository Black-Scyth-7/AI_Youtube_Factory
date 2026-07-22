"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@ayf/ui";

import {
  type AgentTask,
  type Evaluation,
  type Reflection,
  type RunSummary,
  agentApi,
} from "@/lib/agent-api";
import { ApiRequestError } from "@/lib/auth-api";
import { useAuthStore } from "@/lib/auth-store";

interface RunView {
  summary: RunSummary;
  tasks: AgentTask[];
  reflection: Reflection | null;
  evaluation: Evaluation | null;
}

const STATUS_COLOR: Record<string, string> = {
  succeeded: "bg-green-500",
  completed: "bg-green-500",
  failed: "bg-destructive",
  running: "bg-blue-500",
  pending: "bg-muted-foreground",
  skipped: "bg-muted-foreground",
};

/**
 * Agent console: the registry of available agents, a goal form to run one, and
 * the full run result — output, task timeline, reflection, and evaluation.
 */
export default function AgentsPage() {
  const token = useAuthStore((s) => s.accessToken);

  const agents = useQuery({
    queryKey: ["agents"],
    queryFn: () => agentApi.list(token!),
    enabled: !!token,
  });

  const [slug, setSlug] = useState("assistant");
  const [objective, setObjective] = useState("");
  const [orgId, setOrgId] = useState("");
  const [busy, setBusy] = useState(false);
  const [run, setRun] = useState<RunView | null>(null);

  async function start() {
    if (!token || !objective.trim()) {
      toast.error("An objective is required.");
      return;
    }
    setBusy(true);
    setRun(null);
    try {
      const summary = await agentApi.start(token, {
        slug,
        objective: objective.trim(),
        organization_id: orgId.trim() || undefined,
      });
      const [tasks, reflection, evaluation] = await Promise.all([
        agentApi.tasks(token, summary.run_id),
        agentApi.reflection(token, summary.run_id).catch(() => null),
        agentApi.evaluation(token, summary.run_id).catch(() => null),
      ]);
      setRun({ summary, tasks, reflection, evaluation });
      toast.success(`Agent ${summary.goal_status}.`);
    } catch (err) {
      toast.error(
        err instanceof ApiRequestError ? err.message : "Failed to run agent.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Agents</h1>
        <Badge variant="secondary">Autonomous · Phase 05</Badge>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Registry</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {agents.data?.map((a) => (
              <button
                key={a.slug}
                onClick={() => setSlug(a.slug)}
                className={
                  "w-full rounded-md border p-3 text-left text-sm transition-colors " +
                  (slug === a.slug
                    ? "border-primary bg-primary/10"
                    : "border-border hover:bg-accent")
                }
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium">{a.name}</span>
                  <span className="text-xs text-muted-foreground">
                    v{a.version}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">{a.description}</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {a.capabilities.map((c) => (
                    <Badge key={c} variant="secondary">
                      {c}
                    </Badge>
                  ))}
                </div>
              </button>
            ))}
            {agents.isLoading && (
              <p className="text-sm text-muted-foreground">Loading agents…</p>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Run a goal</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <label className="block space-y-1 text-sm">
              <span className="font-medium">Objective</span>
              <textarea
                className="min-h-24 w-full rounded-md border border-input bg-background p-3 text-sm"
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                placeholder="e.g. Research the benefits of server-side rendering"
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="font-medium">Organization ID (optional)</span>
              <input
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={orgId}
                onChange={(e) => setOrgId(e.target.value)}
                placeholder="persist the run to an organization"
              />
            </label>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                Agent: <span className="font-medium text-foreground">{slug}</span>
              </span>
              <Button
                onClick={() => void start()}
                disabled={busy || !objective.trim()}
                className="ml-auto"
              >
                {busy ? "Running…" : "Run agent"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {run && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Result
                <Badge
                  variant={
                    run.summary.goal_status === "completed"
                      ? "secondary"
                      : "destructive"
                  }
                >
                  {run.summary.goal_status}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <pre className="whitespace-pre-wrap rounded-md border border-border bg-muted p-3 text-sm">
                {run.summary.output}
              </pre>
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Task timeline</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {run.tasks.map((t) => (
                  <div
                    key={t.id}
                    className="flex items-start gap-3 rounded-md border border-border p-2 text-sm"
                  >
                    <span
                      className={
                        "mt-1 h-2 w-2 shrink-0 rounded-full " +
                        (STATUS_COLOR[t.status] ?? "bg-muted-foreground")
                      }
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{t.description}</span>
                        <span className="text-xs text-muted-foreground">
                          {t.kind}
                        </span>
                      </div>
                      {t.result && (
                        <p className="truncate text-xs text-muted-foreground">
                          {t.result}
                        </p>
                      )}
                      {t.error && (
                        <p className="text-xs text-destructive">{t.error}</p>
                      )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <div className="space-y-6">
              {run.evaluation && (
                <Card>
                  <CardHeader>
                    <CardTitle>Evaluation</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {(
                      [
                        ["Overall", run.evaluation.overall],
                        ["Correctness", run.evaluation.correctness],
                        ["Completeness", run.evaluation.completeness],
                        ["Quality", run.evaluation.quality],
                        ["Confidence", run.evaluation.confidence],
                        ["Cost", run.evaluation.cost],
                        ["Latency", run.evaluation.latency],
                      ] as [string, number][]
                    ).map(([label, value]) => (
                      <div key={label} className="text-sm">
                        <div className="mb-1 flex justify-between">
                          <span className="text-muted-foreground">{label}</span>
                          <span className="font-medium">
                            {(value * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-muted">
                          <div
                            className="h-1.5 rounded-full bg-primary"
                            style={{ width: `${Math.round(value * 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}

              {run.reflection && (
                <Card>
                  <CardHeader>
                    <CardTitle>Reflection</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <p className="text-muted-foreground">
                      {run.reflection.summary}
                    </p>
                    {run.reflection.lessons.length > 0 && (
                      <div>
                        <p className="font-medium">Lessons</p>
                        <ul className="list-inside list-disc text-muted-foreground">
                          {run.reflection.lessons.map((l, i) => (
                            <li key={i}>{l}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
