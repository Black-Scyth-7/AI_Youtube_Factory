"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@ayf/ui";

import { ApiRequestError } from "@/lib/auth-api";
import { useAuthStore } from "@/lib/auth-store";
import { type ConversationMessage, llmApi } from "@/lib/llm-api";

/**
 * Conversation viewer. Loads the persisted message history for a conversation
 * id and renders the ordered transcript with per-message token counts.
 */
export default function ConversationViewerPage() {
  const token = useAuthStore((s) => s.accessToken);
  const [conversationId, setConversationId] = useState("");
  const [messages, setMessages] = useState<ConversationMessage[] | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    if (!token || !conversationId.trim()) {
      toast.error("A conversation ID is required.");
      return;
    }
    setBusy(true);
    try {
      const rows = await llmApi.conversationMessages(token, conversationId.trim());
      setMessages(rows);
    } catch (err) {
      toast.error(err instanceof ApiRequestError ? err.message : "Failed to load.");
      setMessages(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">
          Conversation viewer
        </h1>
        <Badge variant="secondary">Memory</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Load conversation</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-2">
          <input
            className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm"
            value={conversationId}
            onChange={(e) => setConversationId(e.target.value)}
            placeholder="conversation uuid"
          />
          <Button onClick={() => void load()} disabled={busy}>
            {busy ? "Loading…" : "Load"}
          </Button>
        </CardContent>
      </Card>

      {messages !== null && (
        <Card>
          <CardHeader>
            <CardTitle>Transcript ({messages.length})</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {messages.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                This conversation has no messages.
              </p>
            ) : (
              messages.map((m) => (
                <div
                  key={m.id}
                  className="rounded-lg border border-border p-3 text-sm"
                >
                  <div className="mb-1 flex items-center justify-between text-xs text-muted-foreground">
                    <span className="font-medium uppercase">{m.role}</span>
                    <span>
                      #{m.sequence} · {m.tokens} tokens
                    </span>
                  </div>
                  <div className="whitespace-pre-wrap">{m.content}</div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
