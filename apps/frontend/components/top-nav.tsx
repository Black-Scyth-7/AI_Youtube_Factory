"use client";

import { Bell, UserCircle2 } from "lucide-react";

import { Button } from "@ayf/ui";

import { ThemeToggle } from "@/components/theme-toggle";

/** Top navigation bar for the dashboard shell. */
export function TopNav() {
  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-card px-6">
      <div className="text-sm text-muted-foreground">Dashboard</div>
      <div className="flex items-center gap-1">
        <ThemeToggle />
        <Button variant="ghost" size="icon" aria-label="Notifications">
          <Bell className="h-4 w-4" />
        </Button>
        <Button variant="ghost" size="icon" aria-label="Account">
          <UserCircle2 className="h-5 w-5" />
        </Button>
      </div>
    </header>
  );
}
