import type { Metadata } from "next";

import { Badge, Card, CardContent, CardHeader, CardTitle } from "@ayf/ui";

export const metadata: Metadata = { title: "Overview" };

const STATS = [
  { label: "Channels", value: "0" },
  { label: "Videos", value: "0" },
  { label: "Active agents", value: "0" },
  { label: "Workflows", value: "0" },
];

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <Badge variant="secondary">Foundation · Phase 01</Badge>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STATS.map((s) => (
          <Card key={s.label}>
            <CardHeader>
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {s.label}
              </CardTitle>
            </CardHeader>
            <CardContent className="text-3xl font-bold">{s.value}</CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Getting started</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          The platform scaffold is in place. Business features (channels, AI agents,
          and the video pipeline) arrive in the next phases.
        </CardContent>
      </Card>
    </div>
  );
}
