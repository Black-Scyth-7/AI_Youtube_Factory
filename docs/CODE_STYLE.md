# Code Style

## Python (backend, worker)

- **Formatter:** Black (line length 90).
- **Linter:** Ruff (`E, F, I, N, UP, B, C4, SIM, ASYNC, RUF`).
- **Types:** MyPy in `strict` mode. Every function has type hints.
- **Docstrings:** module- and public-symbol-level docstrings required.
- **Logging:** use the structured logger (`app.logging.get_logger`); pass
  context via `extra={...}`, never f-string secrets.
- **Errors:** raise typed `AppError` subclasses; never swallow exceptions.
- **No magic values, no global mutable state, no deep nesting or giant functions.**

```bash
ruff check app tests && black --check app tests && mypy app && pytest
```

## TypeScript (frontend, admin, packages)

- **Formatter:** Prettier (see `.prettierrc.json`).
- **Linter:** ESLint flat config (`@ayf/eslint-config`).
- **Types:** `strict` + `noUncheckedIndexedAccess`. Prefer shared types from
  `@ayf/shared`; do not redefine API contracts locally.
- **Components:** design-system primitives live in `@ayf/ui`; app code composes
  them. Use the `cn()` helper for class merging.
- **App Router only** — no Pages Router.

```bash
pnpm lint && pnpm typecheck && pnpm test
```

## General

- One responsibility per file; small modules; clear names.
- Avoid circular imports.
- Every feature ships with tests and updated docs.
