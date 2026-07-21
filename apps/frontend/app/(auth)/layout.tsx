import Link from "next/link";

/**
 * Centered, minimal shell for authentication screens (login, register, reset).
 * Auth logic is not implemented in Phase 01 — this is layout only.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-8 px-6">
      <Link href="/" className="text-lg font-semibold">
        AI YouTube Factory
      </Link>
      <div className="w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-sm">
        {children}
      </div>
    </div>
  );
}
