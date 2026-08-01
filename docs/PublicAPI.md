# Public API

A small, stable surface for third-party integrations, at `/api/public/v1`.

Separate from `/api/v1`, which serves this product's own frontend and changes
whenever the product does. What is published here is a contract: versioned in
the path, with its own payload models, authenticated by scoped API key.

## Authentication

```bash
curl https://api.example.com/api/public/v1/me \
  -H "Authorization: Bearer ayf_1a2b3c4d.<secret>"
```

`X-API-Key: <key>` works identically. Both conventions are in wide use and
rejecting one buys nothing.

Keys are created at `POST /api/v1/api-keys` and the raw value is shown **once**.
Only its SHA-256 hash is stored, so a database read does not yield a usable
credential, and the comparison on every request is constant-time.

Revocation and expiry are checked on every call — a key is long-lived, so there
is no refresh cycle during which a revocation could go unnoticed.

## Scopes

A key carries scopes that **narrow** what its owner can do; it never widens
them. A key on a build server should read videos, not delete an organization.

| Scope            | Allows                                |
| ---------------- | ------------------------------------- |
| `video:read`     | List and read videos                  |
| `video:write`    | Create and update videos              |
| `channel:read`   | List and read channels                |
| `project:read`   | List and read projects and workspaces |
| `pipeline:read`  | Read pipeline runs                    |
| `pipeline:write` | Start and advance pipeline runs       |
| `analytics:read` | Read published-video analytics        |
| `usage:read`     | Read usage and quotas                 |

**A write scope does not imply the matching read scope.** Implication rules seem
convenient until someone grants `video:write` to a webhook and finds it can
enumerate the catalogue too.

An unknown scope is rejected when the key is created rather than dropped —
silently dropping it issues a key that looks like it has access it does not, and
the failure surfaces much later as a confusing 403.

A scope later removed from the catalogue stops being honoured on keys that still
carry it, rather than acting as a wildcard.

`GET /me` requires authentication but **no scope**: it is how a client discovers
which scopes it holds, so gating it behind one means a key lacking that scope
cannot find out what it can do.

## Tenancy

A key is bound to an organization, and **every object is verified to belong to
it** before anything is returned. Relying on an unguessable id instead is how
one customer reads another's data.

- Another organization's object is a **404, not a 403** — confirming that an id
  exists is itself a disclosure.
- A `project_id` in a query narrows the result set; it can never widen it.
- A key with no organization is refused on organization-scoped endpoints.
  Defaulting to "all of them" would turn a narrow key into a tenant-wide read.

## Endpoints

| Method | Path                          | Scope            |
| ------ | ----------------------------- | ---------------- |
| GET    | `/me`                         | —                |
| GET    | `/channels`                   | `channel:read`   |
| GET    | `/videos`                     | `video:read`     |
| GET    | `/videos/{id}`                | `video:read`     |
| POST   | `/videos`                     | `video:write`    |
| GET    | `/videos/{id}/pipeline-runs`  | `pipeline:read`  |
| GET    | `/usage`                      | `usage:read`     |

## Shape

Lists are objects, never bare arrays:

```json
{
  "data": [],
  "meta": { "total": 42, "page": 1, "size": 20, "has_next": true }
}
```

A top-level array cannot grow a field, so adding pagination later would break
every client.

Pipeline artifacts omit `storage_key`: it is an internal address, and a signed
URL is issued separately.

## Rate limits

Public requests are metered **per key**, at 120 requests/minute — many keys sit
behind one NAT address, and one noisy integration should not throttle everyone
sharing it. Session traffic keeps the 300/minute per-IP budget.

Every response carries `X-RateLimit-Limit` and `X-RateLimit-Remaining`; a 429
also carries `Retry-After`. Without it a client has to guess, and the usual
guess is "immediately", which turns a limit into a loop.

The bucket is derived from a hash of the presented key, so a forged key gets its
own bucket rather than burning through somebody else's.

If Redis is unavailable the limiter degrades open for 30 seconds and then
retries. It previously set a flag that was never cleared, so one transient error
disabled rate limiting for the life of the process.
