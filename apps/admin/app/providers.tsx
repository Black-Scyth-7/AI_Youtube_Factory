"use client";

import { ThemeProvider } from "@/components/theme-provider";

/** Global providers for the admin app (theme only in Phase 01). */
export function Providers({ children }: { children: React.ReactNode }) {
  return <ThemeProvider>{children}</ThemeProvider>;
}
