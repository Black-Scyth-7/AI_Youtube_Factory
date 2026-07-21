"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";

import { Button, Input } from "@ayf/ui";

import { ApiRequestError, authApi } from "@/lib/auth-api";

function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await authApi.resetPassword(token, password);
      toast.success("Password reset. You can now sign in.");
      router.push("/login");
    } catch (err) {
      setError(
        err instanceof ApiRequestError ? err.message : "Something went wrong.",
      );
    } finally {
      setLoading(false);
    }
  }

  if (!token) {
    return (
      <p className="text-center text-sm text-destructive">
        Missing or invalid reset token.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1 text-center">
        <h1 className="text-xl font-semibold">Set a new password</h1>
      </div>
      <form className="space-y-3" onSubmit={onSubmit} noValidate>
        <Input
          type="password"
          placeholder="New password"
          autoComplete="new-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Resetting…" : "Reset password"}
        </Button>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        <Link href="/login" className="text-primary hover:underline">
          Back to sign in
        </Link>
      </p>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
