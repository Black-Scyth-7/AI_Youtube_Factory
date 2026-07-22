"use client";

import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Badge, Button, Card, CardContent, CardHeader, CardTitle } from "@ayf/ui";

import { useAuthStore } from "@/lib/auth-store";
import { type ChatMessageInput, llmApi } from "@/lib/llm-api";

interface Turn {
  role: "user" | "assistant";
  content: string;
}

/**
 * Streaming chat playground. Sends the running transcript to `/llm/stream` and
 * renders token deltas live, or falls back to a single accounted `/llm/chat`
 * call. Model selection comes from the backend catalog; leaving it unset uses
 * the server-configured default.
 */
export default function PlaygroundPage() {
  const token = useAuthStore((s) => s.accessToken);
  const models = useQuery({
    queryKey: ["llm", "models"],
    queryFn: () => llmApi.models(token!),
    enabled: !!token,
  });

  const [model, setModel] = useState<string>("");
  const [system, setSystem] = useState("");
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [streaming, setStreaming] = useState(true);
  const [busy, setBusy] = useState(false);
  const [meta, setMeta] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  function history(next: Turn[]): ChatMessageInput[] {
    return next.map((t) => ({ role: t.role, content: t.content }));
  }

  async function send() {
    if (!token || !input.trim() || busy) return;
    const userTurn: Turn = { role: "user", content: input.trim() };
    const base = [...turns, userTurn];
    setTurns(base);
    setInput("");
    setBusy(true);
    setMeta(null);

    const payload = {
      messages: history(base),
      model: model || undefined,
      system: system || undefined,
    };

    try {
      if (streaming) {
        setTurns([...base, { role: "assistant", content: "" }]);
        let acc = "";
        for await (const ev of llmApi.stream(token, payload)) {
          if (ev.type === "delta" && ev.text) {
            acc += ev.text;
            setTurns([...base, { role: "assistant", content: acc }]);
            scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
          } else if (ev.type === "error") {
            throw new Error(ev.text || "Stream error");
          }
        }
      } else {
        const res = await llmApi.chat(token, payload);
        setTurns([...base, { role: "assistant", content: res.content }]);
        setMeta(
          `${res.model} · ${res.usage.total_tokens} tokens · $${res.cost_usd.toFixed(
            6,
          )} · ${res.latency_ms.toFixed(0)}ms${res.cache_hit ? " · cached" : ""}`,
        );
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Request failed");
      setTurns(base);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Playground</h1>
        <Badge variant="secondary">Streaming demo</Badge>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1 text-sm">
            <span className="font-medium">Model</span>
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            >
              <option value="">Server default</option>
              {models.data?.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.display_name}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm">
            <span className="font-medium">System prompt (optional)</span>
            <input
              className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
              value={system}
              onChange={(e) => setSystem(e.target.value)}
              placeholder="You are a helpful assistant."
            />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={streaming}
              onChange={(e) => setStreaming(e.target.checked)}
            />
            <span>Stream responses (SSE)</span>
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Conversation</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            ref={scrollRef}
            className="max-h-96 space-y-3 overflow-y-auto rounded-md border border-border p-4"
          >
            {turns.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Start a conversation below.
              </p>
            )}
            {turns.map((t, i) => (
              <div
                key={i}
                className={
                  t.role === "user"
                    ? "ml-auto max-w-[85%] rounded-lg bg-primary/10 px-3 py-2 text-sm"
                    : "mr-auto max-w-[85%] rounded-lg bg-muted px-3 py-2 text-sm"
                }
              >
                <div className="mb-1 text-xs font-medium uppercase text-muted-foreground">
                  {t.role}
                </div>
                <div className="whitespace-pre-wrap">
                  {t.content || (busy ? "…" : "")}
                </div>
              </div>
            ))}
          </div>

          {meta && <p className="text-xs text-muted-foreground">{meta}</p>}

          <div className="flex gap-2">
            <input
              className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void send();
                }
              }}
              placeholder="Type a message…"
              disabled={busy}
            />
            <Button onClick={() => void send()} disabled={busy || !input.trim()}>
              {busy ? "Sending…" : "Send"}
            </Button>
            {turns.length > 0 && (
              <Button
                variant="outline"
                onClick={() => {
                  setTurns([]);
                  setMeta(null);
                }}
                disabled={busy}
              >
                Clear
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
