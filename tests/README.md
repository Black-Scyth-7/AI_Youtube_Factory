# Cross-service tests

End-to-end and integration tests that span multiple services live here.

- **Unit tests** live inside each app/package (`apps/*/tests`, `packages/*/src`).
- **E2E (Playwright)** — placeholder for browser-driven flows across the
  frontend + backend. Wired up once auth and the first data-backed pages exist.

```bash
# (later phases)
pnpm dlx playwright test
```
