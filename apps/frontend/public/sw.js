/**
 * Service worker: an offline shell, and nothing more.
 *
 * Deliberately conservative about what it stores.
 *
 * API responses are NEVER cached. They are per-user and authenticated, and the
 * Cache Storage API is shared across every account that uses the browser — so
 * caching them would serve one user's data to the next one who signs in. The
 * only things cached are static assets and an offline fallback page.
 *
 * Navigations are network-first so a deploy is picked up immediately; the
 * cache is only consulted when the network fails.
 */

const VERSION = "v1";
const SHELL_CACHE = `ayf-shell-${VERSION}`;
const OFFLINE_URL = "/offline";

const PRECACHE = [OFFLINE_URL, "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      // Individually, so one missing asset does not fail the whole install and
      // leave the app with no offline page at all.
      .then((cache) => Promise.allSettled(PRECACHE.map((url) => cache.add(url))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith("ayf-shell-") && key !== SHELL_CACHE)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

function isCacheableAsset(url) {
  return (
    url.origin === self.location.origin &&
    (url.pathname.startsWith("/_next/static/") ||
      url.pathname.startsWith("/icons/"))
  );
}

self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Only GET. A cached POST would mean a replayed mutation.
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Never touch the API, on any origin.
  if (url.pathname.startsWith("/api/")) return;

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(async () => {
        const cache = await caches.open(SHELL_CACHE);
        return (
          (await cache.match(OFFLINE_URL)) ??
          new Response("Offline", { status: 503, statusText: "Offline" })
        );
      }),
    );
    return;
  }

  if (!isCacheableAsset(url)) return;

  // Static assets are content-hashed, so cache-first is safe and a changed
  // file arrives under a different URL.
  event.respondWith(
    caches.match(request).then(
      (hit) =>
        hit ??
        fetch(request).then((response) => {
          if (response.ok && response.type === "basic") {
            const copy = response.clone();
            caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        }),
    ),
  );
});
