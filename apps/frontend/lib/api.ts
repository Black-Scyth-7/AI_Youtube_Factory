import { API_BASE_PATH, type HealthStatus, type VersionInfo } from "@ayf/shared";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${API_BASE_PATH}${path}`, {
    headers: { "content-type": "application/json" },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API request failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

/** Typed client for the backend API. Extended per feature in later phases. */
export const api = {
  health: () => request<HealthStatus>("/health"),
  version: () => request<VersionInfo>("/version"),
};
