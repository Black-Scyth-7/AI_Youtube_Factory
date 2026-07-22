"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@ayf/ui";

import { ApiRequestError } from "@/lib/auth-api";
import { useAuthStore } from "@/lib/auth-store";
import { type PromptTemplate, llmApi } from "@/lib/llm-api";

/**
 * Prompt library and editor. Creates versioned Jinja templates against an
 * organization and previews a rendered result via the backend prompt engine
 * (variables are sanitized and validated server-side). Templates created in
 * this session are listed locally; full listing arrives with the catalog API.
 */
export default function PromptsPage() {
  const token = useAuthStore((s) => s.accessToken);

  const [orgId, setOrgId] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [template, setTemplate] = useState(
    "You are writing for {{ channel }}. Topic: {{ topic }}.",
  );
  const [created, setCreated] = useState<PromptTemplate[]>([]);
  const [busy, setBusy] = useState(false);

  const [renderId, setRenderId] = useState("");
  const [contextJson, setContextJson] = useState(
    '{\n  "channel": "My Channel",\n  "topic": "AI"\n}',
  );
  const [rendered, setRendered] = useState<string | null>(null);

  async function createTemplate() {
    if (!token) return;
    if (!orgId.trim() || !name.trim() || !template.trim()) {
      toast.error("Organization, name, and template are required.");
      return;
    }
    setBusy(true);
    try {
      const result = await llmApi.createPrompt(token, {
        organization_id: orgId.trim(),
        name: name.trim(),
        template,
        category: category.trim() || undefined,
      });
      setCreated((prev) => [result, ...prev]);
      setRenderId(result.id);
      toast.success(`Created "${result.name}" (v${result.latest_version}).`);
    } catch (err) {
      toast.error(
        err instanceof ApiRequestError ? err.message : "Failed to create prompt.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function preview() {
    if (!token || !renderId.trim()) {
      toast.error("A template id is required to render.");
      return;
    }
    let context: Record<string, unknown>;
    try {
      context = JSON.parse(contextJson);
    } catch {
      toast.error("Context must be valid JSON.");
      return;
    }
    try {
      const { rendered: out } = await llmApi.renderPrompt(
        token,
        renderId.trim(),
        context,
      );
      setRendered(out);
    } catch (err) {
      toast.error(
        err instanceof ApiRequestError ? err.message : "Failed to render.",
      );
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Prompt library</h1>
        <Badge variant="secondary">Versioned · Jinja</Badge>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>New template</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <label className="block space-y-1 text-sm">
              <span className="font-medium">Organization ID</span>
              <input
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={orgId}
                onChange={(e) => setOrgId(e.target.value)}
                placeholder="uuid of the owning organization"
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="block space-y-1 text-sm">
                <span className="font-medium">Name</span>
                <input
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="script-intro"
                />
              </label>
              <label className="block space-y-1 text-sm">
                <span className="font-medium">Category</span>
                <input
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="scripting"
                />
              </label>
            </div>
            <label className="block space-y-1 text-sm">
              <span className="font-medium">Template</span>
              <textarea
                className="min-h-32 w-full rounded-md border border-input bg-background p-3 font-mono text-sm"
                value={template}
                onChange={(e) => setTemplate(e.target.value)}
              />
            </label>
            <Button onClick={() => void createTemplate()} disabled={busy}>
              {busy ? "Saving…" : "Create template"}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Render preview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <label className="block space-y-1 text-sm">
              <span className="font-medium">Template ID</span>
              <input
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={renderId}
                onChange={(e) => setRenderId(e.target.value)}
                placeholder="template uuid"
              />
            </label>
            <label className="block space-y-1 text-sm">
              <span className="font-medium">Context (JSON)</span>
              <textarea
                className="min-h-28 w-full rounded-md border border-input bg-background p-3 font-mono text-sm"
                value={contextJson}
                onChange={(e) => setContextJson(e.target.value)}
              />
            </label>
            <Button variant="outline" onClick={() => void preview()}>
              Render
            </Button>
            {rendered !== null && (
              <pre className="whitespace-pre-wrap rounded-md border border-border bg-muted p-3 text-sm">
                {rendered}
              </pre>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Created this session</CardTitle>
        </CardHeader>
        <CardContent>
          {created.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No templates created yet.
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {created.map((p) => (
                <li key={p.id} className="flex items-center justify-between py-2">
                  <div>
                    <div className="text-sm font-medium">{p.name}</div>
                    <div className="font-mono text-xs text-muted-foreground">
                      {p.id}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    {p.category && <Badge variant="secondary">{p.category}</Badge>}
                    <span className="text-muted-foreground">
                      v{p.latest_version}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
