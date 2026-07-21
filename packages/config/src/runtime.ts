/** Runtime configuration constants shared by the web apps. */

export const runtimeConfig = {
  /** Default React Query stale time (ms). */
  queryStaleTimeMs: 30_000,
  /** Default request timeout for browser API calls (ms). */
  requestTimeoutMs: 15_000,
  /** Toast auto-dismiss duration (ms). */
  toastDurationMs: 5_000,
} as const;

export type RuntimeConfig = typeof runtimeConfig;
