import { API_BASE_PATH } from "@ayf/shared";

import { ApiRequestError } from "./auth-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// -- Types (mirror app/schemas/agent.py) ---------------------------------
export interface AgentInfo {
  slug: string;
  name: string;
  description: string;
  version: string;
  category: string;
  capabilities: string[];
  tags: string[];
  required_permission: string;
  provider_independent: boolean;
}

export interface RunSummary {
  run_id: string;
  goal_id: string;
  agent_slug: string;
  state: string;
  goal_status: string;
  output: string;
}

export interface AgentTask {
  id: string;
  key: string;
  description: string;
  kind: string;
  status: string;
  order_index: number;
  attempts: number;
  depends_on: string[];
  error: string | null;
  result: string | null;
}

export interface Reflection {
  run_id: string;
  summary: string;
  mistakes: string[];
  lessons: string[];
  improvements: string[];
}

export interface Evaluation {
  run_id: string;
  correctness: number;
  completeness: number;
  cost: number;
  latency: number;
  quality: number;
  confidence: number;
  overall: number;
  notes: string[];
}

export interface ToolInfo {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  mutating: boolean;
  builtin: boolean;
}

export interface RunningAgent {
  run_id: string;
  slug: string;
  state: string;
  objective: string;
}

export interface KnowledgeDoc {
  id: string;
  title: string;
  content: string;
  kind: string;
  tags: string[];
  source: string | null;
  created_at: string;
}

export interface PlanPreview {
  objective: string;
  rationale: string;
  outline: string[];
  tasks: { key: string; description: string; kind: string; depends_on: string[] }[];
}

export interface MetricsReport {
  runs: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  success_rate: number;
  monitor: {
    running: number;
    runs_total: number;
    runs_succeeded: number;
    runs_failed: number;
    success_rate: number;
    total_tokens: number;
    total_cost_usd: number;
    avg_latency_ms: number;
    tool_calls: number;
  };
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("content-type", "application/json");
  if (token) headers.set("authorization", `Bearer ${token}`);
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

/** Typed client for the /agents, /goals, /tasks, /tools, ... endpoints. */
export const agentApi = {
  list: (token: string) => request<AgentInfo[]>("/agents", {}, token),

  running: (token: string) => request<RunningAgent[]>("/agents/running", {}, token),

  start: (
    token: string,
    body: {
      slug: string;
      objective: string;
      organization_id?: string;
      constraints?: string[];
      expected_output?: string;
      success_criteria?: string[];
      max_iterations?: number;
    },
  ) =>
    request<RunSummary>(
      "/agents/start",
      { method: "POST", body: JSON.stringify(body) },
      token,
    ),

  stop: (token: string, runId: string) =>
    request<{ run_id: string; acted: boolean; message: string }>(
      "/agents/stop",
      { method: "POST", body: JSON.stringify({ run_id: runId }) },
      token,
    ),

  tasks: (token: string, runId: string) =>
    request<AgentTask[]>(`/tasks?run_id=${runId}`, {}, token),

  reflection: (token: string, runId: string) =>
    request<Reflection>(`/reflections/${runId}`, {}, token),

  evaluation: (token: string, runId: string) =>
    request<Evaluation>(`/evaluations/${runId}`, {}, token),

  tools: (token: string, organizationId?: string) =>
    request<ToolInfo[]>(
      organizationId ? `/tools?organization_id=${organizationId}` : "/tools",
      {},
      token,
    ),

  planPreview: (token: string, objective: string) =>
    request<PlanPreview>(
      "/plans/preview",
      { method: "POST", body: JSON.stringify({ objective }) },
      token,
    ),

  knowledge: (token: string, organizationId: string) =>
    request<KnowledgeDoc[]>(
      `/knowledge?organization_id=${organizationId}`,
      {},
      token,
    ),

  createKnowledge: (
    token: string,
    body: {
      organization_id: string;
      title: string;
      content: string;
      kind?: string;
      tags?: string[];
    },
  ) =>
    request<KnowledgeDoc>(
      "/knowledge",
      { method: "POST", body: JSON.stringify(body) },
      token,
    ),

  deleteKnowledge: (token: string, id: string) =>
    request<{ message: string }>(`/knowledge/${id}`, { method: "DELETE" }, token),

  metrics: (token: string, organizationId: string) =>
    request<MetricsReport>(`/metrics?organization_id=${organizationId}`, {}, token),
};
