# Authentication & Identity

Phase 02 implements a complete, production-shaped identity system.

## Concepts

- **Access token** — short-lived (15 min) signed JWT (HS256). Sent as
  `Authorization: Bearer <token>`. Bound to a **session id**; a revoked session
  invalidates the token immediately.
- **Refresh token** — long-lived (30 day), opaque, **stored hashed** (SHA-256).
  Rotated on every use; reusing a rotated token revokes the whole session
  (replay/theft defense).
- **Session** — a device/browser login. Carries IP, browser, OS, device.
- Secret tokens (verification, reset, invitation, API-key secrets) are always
  persisted as SHA-256 hashes — the database never holds a usable secret.

## Flows

### Registration → verification

`POST /auth/register` creates the user (unverified), issues a hashed
verification token, and emails a link. `POST /auth/verify-email` consumes the
single-use token and marks the account verified.

### Login → tokens

`POST /auth/login` verifies the Argon2id hash and returns an access/refresh
pair. Email-enumeration safe (generic error + constant-time dummy verify) and
brute-force limited (Redis counter, lockout after N failures).

### Refresh (rotation)

`POST /auth/refresh` validates + rotates the refresh token. The old token is
revoked and linked to its successor.

### Logout

`POST /auth/logout` revokes the current session, or all sessions when
`all_devices=true`.

### Password reset

`POST /auth/forgot-password` (always 200, enumeration-safe) → emailed token →
`POST /auth/reset-password` sets the new hash and revokes all sessions.

### OAuth (Google, GitHub)

`GET /auth/{provider}/authorize` returns a provider URL with a signed, time-
limited `state` (CSRF). `GET /auth/{provider}/callback` verifies state,
exchanges the code, and links or provisions the account (profile + avatar sync).

## Passwords

- **Argon2id** (`argon2-cffi`), never plaintext, transparent rehash on param
  change.
- Policy: ≥10 chars, upper + lower + digit + symbol, common-password denylist.

## API keys

`POST /api-keys` returns the raw key **once** (`prefix.secret`). Only the prefix
and the SHA-256 of the secret are stored. Keys carry scopes, optional expiry,
last-used tracking, and revocation.

## Sessions

`GET /sessions` lists active sessions; `DELETE /sessions/{id}` and
`DELETE /sessions` (all) terminate them.

## Audit log

Every security-relevant action (login, logout, failed login, verification,
password change/reset, role change, invite lifecycle, API-key lifecycle) writes
an append-only `audit_log` row with actor, org, IP, and metadata.

See [RBAC.md](RBAC.md) for roles, permissions, and authorization.
