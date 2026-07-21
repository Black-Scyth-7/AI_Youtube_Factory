# Security Policy

## Reporting a vulnerability

Report suspected vulnerabilities privately to **security@ai-youtube-factory.local**
(placeholder). Do not open public issues for security reports. We aim to
acknowledge within 3 business days.

## Posture (Phase 01)

Phase 01 is foundation only — authentication and authorization are **interface
placeholders**, not implemented. Even so, these baseline controls are in place:

- **No secrets in the repo.** `.env` is git-ignored; only `.env.example` (no real
  values) is committed. Secret-bearing settings use `repr=False`.
- **Configuration validation** fails startup on missing/invalid required values.
- **Structured error envelope** never leaks stack traces to clients; details are
  logged server-side and correlated by `request_id`.
- **Containers run as non-root** users.
- **CORS** is restricted to configured origins.

## Planned (later phases)

JWT/OAuth, RBAC, rate limiting, encryption at rest/in transit, secure cookies,
CSRF protection, input validation hardening, audit logging, and secrets
management integration.
