# AI YouTube Factory — Frontend

**Next.js (App Router)** web application. TypeScript, TailwindCSS, the shared
`@ayf/ui` design system, React Query, Zustand, Framer Motion, and dark-mode-first
theming via `next-themes`.

## Structure

```
app/
  layout.tsx            Root layout + global providers
  providers.tsx         Theme + React Query + Toaster
  page.tsx              Landing page
  not-found.tsx         404
  loading.tsx           Route loading UI
  error.tsx             Error boundary
  (dashboard)/          Authenticated dashboard shell (sidebar + top nav)
  (auth)/               Auth screens (placeholder)
components/             Theme provider, sidebar, top nav, theme toggle
lib/                    Typed API client + Zustand store
```

## Develop

```bash
pnpm install          # from the repo root
pnpm --filter @ayf/frontend dev
```

Requires `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`).
Uses the App Router only — no Pages Router.
