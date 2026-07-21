/** Shared, framework-agnostic constants. */

export const API_VERSION = "v1" as const;
export const API_BASE_PATH = `/api/${API_VERSION}` as const;

export const SERVICE_NAMES = ["backend", "worker", "frontend", "admin"] as const;
export type ServiceName = (typeof SERVICE_NAMES)[number];

export const APP_NAME = "AI YouTube Factory" as const;
