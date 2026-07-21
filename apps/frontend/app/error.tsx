"use client";

import { useEffect } from "react";

import { Button } from "@ayf/ui";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface the error to the console; a real telemetry sink is added later.
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
      <h1 className="text-2xl font-semibold">Something went wrong</h1>
      <p className="max-w-md text-muted-foreground">
        An unexpected error occurred while rendering this page.
      </p>
      <Button onClick={reset}>Try again</Button>
    </main>
  );
}
