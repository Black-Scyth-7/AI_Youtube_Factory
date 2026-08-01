import { API_BASE_PATH } from "@ayf/shared";

import { ApiRequestError } from "./auth-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Mirrors PluginResponse in app/api/v1/routes/plugins.py. */
export interface Plugin {
  name: string;
  version: string;
  display_name: string;
  description: string;
  author: string;
  hooks: string[];
  priority: number;
  timeout_seconds: number;
  requested_capabilities: string[];
  granted_capabilities: string[];
  refused_capabilities: string[];
}

export interface Hook {
  hook: string;
  plugins: string[];
}

async function request<T>(path: string, accessToken?: string): Promise<T> {
  const headers = new Headers({ "content-type": "application/json" });
  if (accessToken) headers.set("authorization", `Bearer ${accessToken}`);

  const res = await fetch(`${API_URL}${API_BASE_PATH}${path}`, {
    headers,
    cache: "no-store",
  });
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

/** Typed client for the /plugins/* endpoints. */
export const pluginsApi = {
  list: (token: string) => request<Plugin[]>("/plugins", token),
  hooks: (token: string) => request<Hook[]>("/plugins/hooks", token),
  capabilities: (token: string) =>
    request<Record<string, string>>("/plugins/capabilities", token),
};
