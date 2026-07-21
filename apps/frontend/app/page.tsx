import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle, buttonVariants } from "@ayf/ui";

const FEATURES = [
  { title: "Research", body: "Trend, keyword, and competitor intelligence." },
  { title: "Generate", body: "Scripts, voice, images, and video via AI agents." },
  { title: "Optimize", body: "SEO, thumbnails, and metadata tuned automatically." },
  { title: "Learn", body: "Analytics feed a self-improving content loop." },
];

export default function LandingPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col items-center justify-center gap-12 px-6 py-24 text-center">
      <div className="space-y-6">
        <span className="inline-block rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">
          Phase 01 · Foundation
        </span>
        <h1 className="text-balance text-5xl font-bold tracking-tight sm:text-6xl">
          AI YouTube Factory
        </h1>
        <p className="mx-auto max-w-2xl text-balance text-lg text-muted-foreground">
          Autonomously research, generate, edit, optimize, publish, analyze, and
          continuously improve YouTube content — end to end.
        </p>
        <div className="flex items-center justify-center gap-3">
          <Link href="/dashboard" className={buttonVariants()}>
            Open dashboard
          </Link>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className={buttonVariants({ variant: "outline" })}
          >
            API docs
          </a>
        </div>
      </div>

      <div className="grid w-full gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {FEATURES.map((f) => (
          <Card key={f.title} className="text-left">
            <CardHeader>
              <CardTitle>{f.title}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {f.body}
            </CardContent>
          </Card>
        ))}
      </div>
    </main>
  );
}
