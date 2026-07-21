import Link from "next/link";

import { buttonVariants } from "@ayf/ui";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-6 text-center">
      <p className="text-6xl font-bold tracking-tight">404</p>
      <h1 className="text-xl font-semibold">This page could not be found.</h1>
      <p className="max-w-md text-muted-foreground">
        The page you are looking for doesn&apos;t exist or has been moved.
      </p>
      <Link href="/" className={buttonVariants()}>
        Back to home
      </Link>
    </main>
  );
}
