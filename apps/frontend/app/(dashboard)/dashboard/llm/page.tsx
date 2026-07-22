"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge, Card, CardContent, CardHeader, CardTitle } from "@ayf/ui";

import { useAuthStore } from "@/lib/auth-store";
import { llmApi } from "@/lib/llm-api";

/**
 * LLM framework overview: the model catalog (context, limits, pricing,
 * capabilities), live provider health, and the registered tool catalog. This is
 * the read-only "Model Configuration + Provider Settings" surface — model choice
 * is driven by backend config, never hardcoded in the UI.
 */
export default function LlmOverviewPage() {
  const token = useAuthStore((s) => s.accessToken);

  const models = useQuery({
    queryKey: ["llm", "models"],
    queryFn: () => llmApi.models(token!),
    enabled: !!token,
  });
  const health = useQuery({
    queryKey: ["llm", "health"],
    queryFn: () => llmApi.health(token!),
    enabled: !!token,
  });
  const tools = useQuery({
    queryKey: ["llm", "tools"],
    queryFn: () => llmApi.tools(token!),
    enabled: !!token,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">LLM framework</h1>
        <Badge variant="secondary">Claude · Phase 04</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Providers</CardTitle>
        </CardHeader>
        <CardContent>
          {health.isLoading ? (
            <p className="text-sm text-muted-foreground">Checking providers…</p>
          ) : (
            <div className="flex flex-wrap gap-3">
              {health.data?.map((p) => (
                <div
                  key={p.provider}
                  className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
                >
                  <span
                    className={
                      p.healthy
                        ? "h-2 w-2 rounded-full bg-green-500"
                        : "h-2 w-2 rounded-full bg-destructive"
                    }
                    aria-hidden
                  />
                  <span className="font-medium">{p.provider}</span>
                  <span className="text-muted-foreground">
                    {p.healthy ? "healthy" : "unavailable"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Model catalog</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="py-2 pr-4 font-medium">Model</th>
                  <th className="py-2 pr-4 font-medium">Context</th>
                  <th className="py-2 pr-4 font-medium">Max output</th>
                  <th className="py-2 pr-4 font-medium">Input $/MTok</th>
                  <th className="py-2 pr-4 font-medium">Output $/MTok</th>
                  <th className="py-2 pr-4 font-medium">Capabilities</th>
                </tr>
              </thead>
              <tbody>
                {models.data?.map((m) => (
                  <tr key={m.id} className="border-b border-border/50">
                    <td className="py-2 pr-4">
                      <div className="font-medium">{m.display_name}</div>
                      <div className="text-xs text-muted-foreground">{m.id}</div>
                    </td>
                    <td className="py-2 pr-4">
                      {m.context_window.toLocaleString()}
                    </td>
                    <td className="py-2 pr-4">{m.max_output.toLocaleString()}</td>
                    <td className="py-2 pr-4">
                      ${m.input_price_per_mtok.toFixed(2)}
                    </td>
                    <td className="py-2 pr-4">
                      ${m.output_price_per_mtok.toFixed(2)}
                    </td>
                    <td className="py-2 pr-4">
                      <div className="flex gap-1">
                        {m.supports_tools && (
                          <Badge variant="secondary">tools</Badge>
                        )}
                        {m.supports_streaming && (
                          <Badge variant="secondary">streaming</Badge>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {models.isLoading && (
            <p className="text-sm text-muted-foreground">Loading models…</p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Registered tools</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {tools.data?.length ? (
            tools.data.map((t) => (
              <div key={t.name} className="rounded-md border border-border p-3">
                <div className="font-mono text-sm font-medium">{t.name}</div>
                <div className="text-sm text-muted-foreground">{t.description}</div>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">
              No tools registered yet.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
