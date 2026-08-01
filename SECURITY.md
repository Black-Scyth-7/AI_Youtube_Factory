# Security Policy

## Reporting a vulnerability

Report suspected vulnerabilities privately to **security@ai-youtube-factory.local**
(placeholder). Do not open public issues for security reports. We aim to
acknowledge within 3 business days.

## Posture

Phases 01–09 are delivered; authentication, authorization, and observability are
implemented rather than stubbed. What follows describes what is actually in the
code, and — under *Known gaps* — what is not.

### Authentication

- **Argon2id** password hashing via `argon2-cffi` (`app/security/password.py`).
  Plaintext is never stored, and verification is constant-time.
- **JWT access tokens** carry `type`, `sub`, `sid`, `jti`, and `exp`, and
  verification *requires* those claims. The `type` claim is checked on use, so a
  token minted for one purpose cannot be replayed as another — a password-reset
  token is not a session.
- **Refresh tokens are opaque and stored hashed** (SHA-256). The database never
  holds a usable secret, so a database read does not yield session takeover.
- **Refresh tokens rotate on use**, and a consumed token records the successor
  that replaced it (`rotated_to`), so presenting an already-rotated token is
  detectable as replay rather than merely failing.
- **Login lockout** — a Redis-backed failed-attempt counter locks an account for
  `LOGIN_LOCKOUT_SECONDS` after `LOGIN_MAX_ATTEMPTS` failures.
- **OAuth** (GitHub, Google) with an `itsdangerous`-signed, time-limited state
  binding the provider to a random nonce; the callback verifies the signature
  before exchanging the code.
- Email-verification and password-reset tokens are single-use (`used_at`) and
  time-bounded.

### Authorization

- **RBAC** with roles and permissions, enforced by a `require_permission`
  dependency at the route level rather than by convention inside handlers.
- Organization, team, and project scoping on domain queries.

### Configuration

- **No secrets in the repo.** `.env` is git-ignored; only `.env.example` is
  committed, and it contains no real values.
- **Production refuses to start on a placeholder secret.** With
  `ENVIRONMENT=production`, `SECRET_KEY` and `JWT_SECRET_KEY` must not be a
  known placeholder and must be at least 32 characters. Previously a deployment
  that forgot to set them booted happily and signed every token with a value
  published in this repository.
- Configuration validation fails startup on missing or invalid required values.

### Transport and headers

- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `X-XSS-Protection: 0`
  (the legacy auditor is an XSS vector in itself), and a restrictive
  `Permissions-Policy`.
- **CORS** restricted to configured origins.
- The API authenticates with bearer tokens and **sets no cookies**, so there is
  no cookie surface to secure. (`COOKIE_SECURE` and `COOKIE_DOMAIN` exist in
  settings but nothing reads them; they are reserved for a future browser
  session flow, which would also need CSRF protection — see *Known gaps*.)

### Application hardening

- **Workflow expressions are evaluated over an AST allow-list**, never `eval`,
  with caps on expression length, nesting depth, and exponent size — an
  unbounded `9**9**9**9` in a user-supplied condition is rejected rather than
  hanging a worker.
- **Rate limiting** (fixed-window, Redis-backed) on top of the per-account
  login lockout.
- **Structured error envelope** never returns stack traces to clients; details
  are logged server-side and correlated by `request_id`.
- **Audit logging** of security-relevant actions.
- Inbound `X-Request-ID` is validated against a conservative pattern before
  being echoed on the response or written into logs.
- Containers run as non-root users.

### Observability endpoints

`/metrics` exposes traffic shape, error rates, and spend — useful to an operator
and equally useful to someone mapping the service. Restrict it at the network
layer, or set `METRICS_TOKEN` and scrape with a bearer token; the comparison is
constant-time. `METRICS_ENABLED=false` returns 404, indistinguishable from an
endpoint that was never mounted.

Tracing accepts an inbound `traceparent` and will join the caller's trace. Trace
ids are not authorization and are echoed back by design; treat them as public.

## Known gaps

Stated plainly so nobody assumes otherwise:

- **No encryption at rest** beyond what the database and object store provide.
  Application-level field encryption is not implemented.
- **No secrets-manager integration.** Secrets come from the environment.
- **No CSRF tokens.** The API is token-authenticated and CORS-restricted; a
  cookie-authenticated browser flow would need them.
- **No HSTS or Content-Security-Policy header** is set by the application. TLS
  termination and CSP are expected at the edge, and the SPA is served
  separately.
- **The security address above is a placeholder**, as is the SMTP sender
  identity.
- Dependency and container scanning are not wired into CI.

## Reviewing changes

A security-relevant change should come with a test that fails without the fix.
The suite already contains regression tests for token-type confusion, expression
evaluation limits, production secret validation, and request-id reflection.
