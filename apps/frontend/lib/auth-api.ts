import { API_BASE_PATH } from "@ayf/shared";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthUser {
  id: string;
  email: string;
  username: string;
  display_name: string | null;
  avatar_url: string | null;
  is_verified: boolean;
  is_superuser: boolean;
}

/** Error carrying the backend's structured error code + message. */
export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
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

export const authApi = {
  register: (data: {
    email: string;
    username: string;
    password: string;
    display_name?: string;
  }) =>
    request<AuthUser>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  login: (data: { email: string; password: string }) =>
    request<TokenPair>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  refresh: (refresh_token: string) =>
    request<TokenPair>("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token }),
    }),

  logout: (accessToken: string, refresh_token: string) =>
    request<{ message: string }>(
      "/auth/logout",
      { method: "POST", body: JSON.stringify({ refresh_token }) },
      accessToken,
    ),

  verifyEmail: (token: string) =>
    request<{ message: string }>("/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  forgotPassword: (email: string) =>
    request<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),

  resetPassword: (token: string, password: string) =>
    request<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),

  me: (accessToken: string) => request<AuthUser>("/users/me", {}, accessToken),

  oauthAuthorize: (provider: "google" | "github") =>
    request<{ authorization_url: string }>(`/auth/${provider}/authorize`),
};
