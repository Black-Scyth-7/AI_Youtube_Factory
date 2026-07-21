/** Shared API contract types used by the frontend and admin apps. */

/** Standard error envelope returned by the backend. */
export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    request_id?: string | null;
  };
}

/** Health of a single subsystem dependency. */
export interface HealthComponent {
  name: string;
  status: "ok" | "degraded" | "down";
  detail?: string | null;
}

/** Aggregate readiness/liveness report. */
export interface HealthStatus {
  status: "ok" | "degraded" | "down";
  components: HealthComponent[];
}

/** Service identity and build metadata. */
export interface VersionInfo {
  name: string;
  version: string;
  environment: string;
}

/** Generic paginated response wrapper for future list endpoints. */
export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
