import type { Metadata } from "next";

import { Button, Input } from "@ayf/ui";

export const metadata: Metadata = { title: "Sign in" };

/**
 * Placeholder sign-in screen. Authentication is intentionally NOT implemented in
 * Phase 01 — the form is disabled and wired up in a later phase.
 */
export default function LoginPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-1 text-center">
        <h1 className="text-xl font-semibold">Welcome back</h1>
        <p className="text-sm text-muted-foreground">
          Authentication ships in a later phase.
        </p>
      </div>
      <form className="space-y-3" aria-disabled>
        <Input type="email" placeholder="you@example.com" disabled />
        <Input type="password" placeholder="Password" disabled />
        <Button type="button" className="w-full" disabled>
          Sign in
        </Button>
      </form>
    </div>
  );
}
