"use client";

import { useEffect } from "react";

/**
 * Registers the service worker that provides the offline shell.
 *
 * Only in production: in development Next serves modules that change on every
 * edit, and a cache in front of them produces stale-bundle bugs that look like
 * application bugs.
 */
export function ServiceWorkerRegistration() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") return;
    if (!("serviceWorker" in navigator)) return;

    // After load, so registration never competes with the first paint.
    const register = () => {
      navigator.serviceWorker.register("/sw.js").catch((error) => {
        // A failed registration costs offline support, not the app.
        console.warn("[ayf] service worker registration failed", error);
      });
    };

    if (document.readyState === "complete") {
      register();
      return;
    }
    window.addEventListener("load", register);
    return () => window.removeEventListener("load", register);
  }, []);

  return null;
}
