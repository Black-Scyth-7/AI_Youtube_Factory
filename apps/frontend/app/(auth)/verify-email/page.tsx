"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { buttonVariants } from "@ayf/ui";

import { authApi } from "@/lib/auth-api";

type Status = "verifying" | "success" | "error";

function VerifyEmail() {
  const token = useSearchParams().get("token") ?? "";
  const [status, setStatus] = useState<Status>("verifying");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      return;
    }
    authApi
      .verifyEmail(token)
      .then(() => setStatus("success"))
      .catch(() => setStatus("error"));
  }, [token]);

  const copy: Record<Status, { title: string; body: string }> = {
    verifying: { title: "Verifying your email…", body: "One moment please." },
    success: { title: "Email verified", body: "Your account is now verified." },
    error: {
      title: "Verification failed",
      body: "This link is invalid or has expired.",
    },
  };

  return (
    <div className="space-y-4 text-center">
      <h1 className="text-xl font-semibold">{copy[status].title}</h1>
      <p className="text-sm text-muted-foreground">{copy[status].body}</p>
      {status !== "verifying" && (
        <Link href="/login" className={buttonVariants()}>
          Continue to sign in
        </Link>
      )}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={null}>
      <VerifyEmail />
    </Suspense>
  );
}
