import type { Metadata } from "next";

export const metadata: Metadata = { title: "Offline" };

/**
 * Shown by the service worker when a navigation fails with no network.
 *
 * Deliberately static and self-contained: it has to render from the cache, so
 * it cannot depend on data, and it must not suggest anything is loading.
 */
export default function OfflinePage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-8 text-center">
      <h1 className="text-2xl font-semibold">You are offline</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        This page needs a connection. Anything already loaded stays available —
        reopen it once you are back online.
      </p>
    </div>
  );
}
