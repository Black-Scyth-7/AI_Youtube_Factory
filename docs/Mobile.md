# Mobile

The dashboard is an installable **Progressive Web App**, not a native
application. Stating that plainly matters: there is no App Store or Play Store
build in this repository, and nothing here produces one.

That was a deliberate choice. A React Native or Expo client would be a fourth
application with its own build, signing, store review, and release cadence,
duplicating every screen the web app already has. The PWA reuses the existing
Next.js app, ships with it, and is verifiable in CI. When a native client is
justified — background uploads, push notifications, camera capture — it should
be its own project, driven by those requirements.

## What was actually broken

The sidebar is `hidden md:block`. Below that breakpoint the dashboard had **no
navigation at all**: every page was reachable only by typing its URL. That, not
the absence of an app binary, was the real mobile gap.

## Navigation

`components/mobile-nav.tsx` adds, below `md`:

- A fixed bottom bar with the five most-used destinations. A phone is held at
  the bottom, and touch targets are at least 44px.
- A "More" sheet with the full list, dismissed on navigation — otherwise it
  stays over the page the user just asked for.
- `pb-[env(safe-area-inset-bottom)]`, so the bar clears the home indicator on a
  notched phone.

Both the sidebar and the mobile menu render `components/nav-items.tsx`. Two
copies drifted apart the moment a page was added to one and not the other, which
is how the billing console shipped with no way to reach it.

## Installability

`app/manifest.ts` is a route rather than a static file, so its values are
type-checked against Next's `MetadataRoute.Manifest`.

- `start_url` is `/dashboard` — someone who installed the app is not looking for
  the marketing page.
- `display: standalone` removes the browser chrome.
- Icons are 192px and 512px, plus a **maskable** 512px variant. Android crops
  icons to its own shape, and without a maskable icon the mark loses its
  corners.

## Offline

`public/sw.js` provides an offline shell and nothing more.

**API responses are never cached.** They are per-user and authenticated, and the
Cache Storage API is shared across every account that uses the browser — caching
them would serve one user's data to the next person who signs in. The service
worker skips `/api/` entirely, and only handles `GET` (a cached `POST` would
mean a replayed mutation).

- **Navigations**: network-first, falling back to `/offline`. A deploy is picked
  up immediately; the cache is consulted only when the network fails.
- **Static assets** (`/_next/static/`, `/icons/`): cache-first, which is safe
  because those URLs are content-hashed — a changed file arrives under a
  different name.
- Old cache versions are deleted on activation.

Registration happens only in production. In development Next serves modules that
change on every edit, and a cache in front of them produces stale-bundle bugs
that look like application bugs.

## Accessibility

Zoom is **not** blocked. `maximum-scale=1` is a WCAG failure and the usual
reason a form is unusable for anyone who needs to magnify it. The viewport sets
`width=device-width, initial-scale=1, viewport-fit=cover` and nothing more.

## Verifying

```bash
pnpm turbo run build --filter=@ayf/frontend
pnpm --filter @ayf/frontend exec next start -p 3000
```

Then check `/manifest.webmanifest` returns JSON, `/sw.js` is served as
JavaScript, `/icons/icon-192.png` is a PNG, and `/offline` renders. Chrome
DevTools → Application → Manifest reports installability.
