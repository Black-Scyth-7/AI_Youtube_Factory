"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@ayf/ui";

import { type KnowledgeDoc, agentApi } from "@/lib/agent-api";
import { ApiRequestError } from "@/lib/auth-api";
import { useAuthStore } from "@/lib/auth-store";

const KINDS = ["fact", "policy", "rule", "documentation", "template", "preference"];

/**
 * Knowledge base: organization-scoped documents (policies, facts, preferences)
 * agents consult during a run. Create, list, and remove documents.
 */
export default function KnowledgeBasePage() {
  const token = useAuthStore((s) => s.accessToken);
  const [orgId, setOrgId] = useState("");
  const [docs, setDocs] = useState<KnowledgeDoc[] | null>(null);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [kind, setKind] = useState("fact");
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!token || !orgId.trim()) {
      toast.error("An organization ID is required.");
      return;
    }
    try {
      setDocs(await agentApi.knowledge(token, orgId.trim()));
    } catch (err) {
      toast.error(err instanceof ApiRequestError ? err.message : "Failed to load.");
    }
  }

  async function create() {
    if (!token || !orgId.trim() || !title.trim() || !content.trim()) {
      toast.error("Organization, title, and content are required.");
      return;
    }
    setBusy(true);
    try {
      await agentApi.createKnowledge(token, {
        organization_id: orgId.trim(),
        title: title.trim(),
        content: content.trim(),
        kind,
      });
      setTitle("");
      setContent("");
      toast.success("Knowledge document created.");
      await load();
    } catch (err) {
      toast.error(
        err instanceof ApiRequestError ? err.message : "Failed to create.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!token) return;
    try {
      await agentApi.deleteKnowledge(token, id);
      setDocs((prev) => prev?.filter((d) => d.id !== id) ?? null);
    } catch (err) {
      toast.error(
        err instanceof ApiRequestError ? err.message : "Failed to delete.",
      );
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Knowledge base</h1>
        <Badge variant="secondary">Knowledge</Badge>
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
          <Button variant="outline" onClick={() => void load()}>
            Load
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>New document</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <input
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Title"
            />
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              {KINDS.map((k) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </div>
          <textarea
            className="min-h-24 w-full rounded-md border border-input bg-background p-3 text-sm"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Document content"
          />
          <Button onClick={() => void create()} disabled={busy}>
            {busy ? "Saving…" : "Create document"}
          </Button>
        </CardContent>
      </Card>

      {docs && (
        <Card>
          <CardHeader>
            <CardTitle>Documents ({docs.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {docs.length === 0 ? (
              <p className="text-sm text-muted-foreground">No documents yet.</p>
            ) : (
              docs.map((d) => (
                <div
                  key={d.id}
                  className="flex items-start justify-between gap-3 rounded-md border border-border p-3"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{d.title}</span>
                      <Badge variant="secondary">{d.kind}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{d.content}</p>
                  </div>
                  <Button variant="outline" onClick={() => void remove(d.id)}>
                    Delete
                  </Button>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
