"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, Input } from "@ayf/ui";

import { authApi } from "@/lib/auth-api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    // The backend always returns success (email-enumeration safe).
    await authApi.forgotPassword(email).catch(() => undefined);
    setSent(true);
    setLoading(false);
  }

  if (sent) {
    return (
      <div className="space-y-4 text-center">
        <h1 className="text-xl font-semibold">Check your email</h1>
        <p className="text-sm text-muted-foreground">
          If an account exists for {email}, a reset link has been sent.
        </p>
        <Link href="/login" className="text-sm text-primary hover:underline">
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1 text-center">
        <h1 className="text-xl font-semibold">Forgot password</h1>
        <p className="text-sm text-muted-foreground">
          We&apos;ll email you a reset link.
        </p>
      </div>
      <form className="space-y-3" onSubmit={onSubmit} noValidate>
        <Input
          type="email"
          placeholder="you@example.com"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Sending…" : "Send reset link"}
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
