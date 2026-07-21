# Core Infrastructure

Phase 03 building blocks under `app/core/` and `app/services/`. Each has a
process singleton accessor and a `set_*` override for tests.

## Cache (`app/core/cache`)

Namespaced, JSON-serialized cache over a pluggable backend.

- Backends: `RedisCache` (distributed) and `InMemoryCache` (fallback/tests).
- `CacheService`: `get`/`set`/`delete`, `invalidate_namespace`, `get_or_set`
  (cache-warming), TTL defaults. Keys: `prefix:namespace:key`.
- `get_cache()` selects Redis, falling back to in-memory if unavailable.

## Event bus (`app/core/events`)

In-process async pub/sub — the seam future AI agents subscribe to.

- `EventBus.subscribe` / `on` (decorator) / `publish` (concurrent, isolated).
- Per-handler bounded retries; exhausted handlers land in `dead_letters`.
- Built-in events: `WorkspaceCreated`, `ProjectCreated`, `VideoCreated`,
  `WorkflowStarted`, `RenderFinished`, `UploadCompleted`, `UserCreated`.

## Task queue (`app/core/tasks`)

Submit/track background work; maps onto Celery/Temporal later.

- `TaskSpec` (name, payload, priority, delay, retries, timeout) →
  `InMemoryTaskQueue.submit` → `TaskRecord` (status, progress, attempts).
- Supports scheduled delay, retry, timeout, and cancellation.

## Storage (`app/core/storage`)

Provider abstraction with a working local implementation.

- `LocalStorageProvider`: `put/get/delete/presign_url/exists`, path-traversal
  guarded. `get_storage()` returns the configured backend.
- Media utils: `compute_sha256` (dedup), `guess_mime_type`, `validate_mime_type`.
- `StorageService` validates MIME, deduplicates by content hash within a
  workspace, stores bytes, records a `MediaFile`, and emits `UploadCompleted`.

## Workflow engine (`app/services/workflow.py`)

Persisted graphs (nodes + edges) executed by a topological walk. Node handlers
are registered per type (`register_node`); a shared context threads through the
run; status + logs are recorded. Cycles are detected and fail the run cleanly.

## Feature flags (`app/services/feature_flags.py`)

Global / organization / user scope with deterministic percentage rollout
(stable per subject) and explicit target allowlists.

## API framework (`app/core/api`)

`PageParams`, `Page`, `PageMeta`, cursor helpers, `FilterSpec`, `SortParam`, and
the `ApiResponse` `{data, meta}` envelope (`paginated(...)`).

## Search (`app/core/search`)

`SearchQuery` + `SqlTextSearch` (ILIKE) behind a `SearchProvider` protocol;
ElasticSearch plugs in later.

## Middleware

Request-context (id/trace/timing), security headers, GZip, and rate limiting.
