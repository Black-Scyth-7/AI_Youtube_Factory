import { Badge, Card, CardContent, CardHeader, CardTitle } from "@ayf/ui";

export default function AdminHome() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Administration</h1>
        <Badge variant="secondary">Placeholder</Badge>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Admin panel</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Organization, user, and system management will be built here in a later
          phase. Phase 01 provides the authenticated shell only.
        </CardContent>
      </Card>
    </div>
  );
}
