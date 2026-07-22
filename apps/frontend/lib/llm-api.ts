import { API_BASE_PATH } from "@ayf/shared";

import { ApiRequestError } from "./auth-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// -- Response types (mirrors app/schemas/llm.py) -------------------------
export interface LlmModel {
  id: string;
  display_name: string;
  context_window: number;
  max_output: number;
  input_price_per_mtok: number;
  output_price_per_mtok: number;
  supports_tools: boolean;
  supports_streaming: boolean;
}

export interface ProviderHealth {
  provider: string;
  healthy: boolean;
}

export interface ToolSchema {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

export interface ChatUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cache_read_tokens: number;
}

export interface ChatResult {
  content: string;
  model: string;
  provider: string;
  stop_reason: string;
  usage: ChatUsage;
  cost_usd: number;
  latency_ms: number;
  cache_hit: boolean;
}

export interface PromptTemplate {
  id: string;
  organization_id: string;
  name: string;
  category: string | null;
  status: string;
  latest_version: number;
  created_at: string;
}

export interface Conversation {
  id: string;
  organization_id: string;
  title: string | null;
  model: string;
  created_at: string;
}

export interface ConversationMessage {
  id: string;
  sequence: number;
  role: string;
  content: string;
  tokens: number;
}

export interface UsageSummary {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  request_count: number;
}

export interface CostSummary {
  input_cost_usd: number;
  output_cost_usd: number;
  total_cost_usd: number;
}

export interface ChatMessageInput {
  role: "user" | "assistant" | "system";
  content: string;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  accessToken?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("content-type", "application/json");
  if (accessToken) headers.set("authorization", `Bearer ${accessToken}`);

  const res = await fetch(`${API_URL}${API_BASE_PATH}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (res.status === 204) return undefined as T;

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error ?? {};
    throw new ApiRequestError(
      err.message ?? "Request failed",
      err.code ?? "error",
      res.status,
    );
  }
  return body as T;
}

/** Typed client for the /llm/* endpoints. */
export const llmApi = {
  models: (token: string) => request<LlmModel[]>("/llm/models", {}, token),

  health: (token: string) => request<ProviderHealth[]>("/llm/health", {}, token),

  tools: (token: string) => request<ToolSchema[]>("/llm/tools", {}, token),

  chat: (
    token: string,
    body: {
      messages: ChatMessageInput[];
      model?: string;
      system?: string;
      provider?: string;
      max_tokens?: number;
      organization_id?: string;
      conversation_id?: string;
    },
  ) =>
    request<ChatResult>(
      "/llm/chat",
      { method: "POST", body: JSON.stringify(body) },
      token,
    ),

  createPrompt: (
    token: string,
    body: {
      organization_id: string;
      name: string;
      template: string;
      category?: string;
      description?: string;
    },
  ) =>
    request<PromptTemplate>(
      "/llm/prompts",
      { method: "POST", body: JSON.stringify(body) },
      token,
    ),

  renderPrompt: (
    token: string,
    templateId: string,
    context: Record<string, unknown>,
    version?: number,
  ) =>
    request<{ rendered: string }>(
      `/llm/prompts/${templateId}/render`,
      { method: "POST", body: JSON.stringify({ context, version }) },
      token,
    ),

  createConversation: (
    token: string,
    body: {
      organization_id: string;
      model?: string;
      system?: string;
      title?: string;
    },
  ) =>
    request<Conversation>(
      "/llm/conversations",
      { method: "POST", body: JSON.stringify(body) },
      token,
    ),

  conversationMessages: (token: string, conversationId: string) =>
    request<ConversationMessage[]>(
      `/llm/conversations/${conversationId}/messages`,
      {},
      token,
    ),

  usage: (token: string, organizationId: string, start: string, end: string) =>
    request<UsageSummary>(
      `/llm/usage?organization_id=${organizationId}&start=${start}&end=${end}`,
      {},
      token,
    ),

  costs: (token: string, organizationId: string, start: string, end: string) =>
    request<CostSummary>(
      `/llm/costs?organization_id=${organizationId}&start=${start}&end=${end}`,
      {},
      token,
    ),

  /**
   * Open an SSE stream for a chat request. Yields incremental text deltas as
   * they arrive. Consumes the `text/event-stream` response body directly since
   * `EventSource` cannot send an Authorization header or a POST body.
   */
  async *stream(
    token: string,
    body: {
      messages: ChatMessageInput[];
      model?: string;
      system?: string;
      provider?: string;
    },
  ): AsyncGenerator<{ type: string; text?: string }> {
    const res = await fetch(`${API_URL}${API_BASE_PATH}/llm/stream`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(body),
    });
    if (!res.ok || res.body === null) {
      throw new ApiRequestError("Stream failed", "stream_error", res.status);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const line = frame.trim();
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (!payload) continue;
        try {
          yield JSON.parse(payload) as { type: string; text?: string };
        } catch {
          // Ignore keep-alive or malformed frames.
        }
      }
    }
  },
};
