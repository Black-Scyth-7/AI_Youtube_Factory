"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge, Card, CardContent, CardHeader, CardTitle } from "@ayf/ui";

import { agentApi } from "@/lib/agent-api";
import { useAuthStore } from "@/lib/auth-store";

/**
 * Tool catalog: the built-in and organization-defined tools agents can use,
 * with their input schemas and whether they mutate external state.
 */
export default function AgentToolsPage() {
  const token = useAuthStore((s) => s.accessToken);
  const tools = useQuery({
    queryKey: ["agent-tools"],
    queryFn: () => agentApi.tools(token!),
    enabled: !!token,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Agent tools</h1>
        <Badge variant="secondary">Tool framework</Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {tools.data?.map((t) => (
          <Card key={t.name}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between text-base">
                <span className="font-mono">{t.name}</span>
                <span className="flex gap-1">
                  {t.builtin && <Badge variant="secondary">built-in</Badge>}
                  {t.mutating && <Badge variant="destructive">mutating</Badge>}
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className="text-sm text-muted-foreground">{t.description}</p>
              <details className="text-xs">
                <summary className="cursor-pointer text-muted-foreground">
                  Input schema
                </summary>
                <pre className="mt-1 overflow-x-auto rounded-md border border-border bg-muted p-2">
                  {JSON.stringify(t.input_schema, null, 2)}
                </pre>
              </details>
            </CardContent>
          </Card>
        ))}
      </div>
      {tools.isLoading && (
        <p className="text-sm text-muted-foreground">Loading tools…</p>
      )}
    </div>
  );
}
