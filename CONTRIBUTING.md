# Contributing

## Workflow

1. Branch from `main`: `feat/<slug>`, `fix/<slug>`, `chore/<slug>`.
2. Keep commits small and focused.
3. Ensure `make lint` and `make test` pass before opening a PR.
4. Update relevant docs and tests with every change.

## Conventional Commits

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <description>
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`,
`ci`, `chore`, `revert`.

Examples:

```
feat(backend): add readiness probe for RabbitMQ
fix(ui): correct Button focus ring in dark mode
chore(ci): cache pnpm store between runs
```

Breaking changes: add `!` after the type/scope (`feat(api)!: ...`) and a
`BREAKING CHANGE:` footer.

## Definition of Done

A change is complete only when: code implemented, tests pass, types/lint clean,
docs updated, Docker builds, and CI is green.
