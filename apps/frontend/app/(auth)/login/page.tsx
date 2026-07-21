"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button, Input } from "@ayf/ui";

import { ApiRequestError, authApi } from "@/lib/auth-api";
import { useAuthStore } from "@/lib/auth-store";

export default function LoginPage() {
  const router = useRouter();
  const setSession = useAuthStore((s) => s.setSession);
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const tokens = await authApi.login(form);
      await setSession(tokens);
      toast.success("Welcome back.");
      router.push("/dashboard");
    } catch (err) {
      setError(
        err instanceof ApiRequestError ? err.message : "Something went wrong.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function oauth(provider: "google" | "github") {
    try {
      const { authorization_url } = await authApi.oauthAuthorize(provider);
      window.location.href = authorization_url;
    } catch {
      toast.error(`${provider} sign-in is not configured.`);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1 text-center">
        <h1 className="text-xl font-semibold">Welcome back</h1>
        <p className="text-sm text-muted-foreground">Sign in to continue.</p>
      </div>

      <form className="space-y-3" onSubmit={onSubmit} noValidate>
        <label className="block text-sm font-medium" htmlFor="email">
          Email
        </label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <div className="flex items-center justify-between">
          <label className="block text-sm font-medium" htmlFor="password">
            Password
          </label>
          <Link
            href="/forgot-password"
            className="text-xs text-muted-foreground hover:underline"
          >
            Forgot password?
          </Link>
        </div>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />

        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}

        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </Button>
      </form>

      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span className="h-px flex-1 bg-border" />
        or
        <span className="h-px flex-1 bg-border" />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Button variant="outline" onClick={() => oauth("google")}>
          Google
        </Button>
        <Button variant="outline" onClick={() => oauth("github")}>
          GitHub
        </Button>
      </div>

      <p className="text-center text-sm text-muted-foreground">
        No account?{" "}
        <Link href="/register" className="text-primary hover:underline">
          Sign up
        </Link>
      </p>
    </div>
  );
}
