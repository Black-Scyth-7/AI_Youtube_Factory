"use client";

import {
  BarChart3,
  BookOpen,
  BrainCircuit,
  FileText,
  Gauge,
  LayoutDashboard,
  MessagesSquare,
  Settings,
  Sparkles,
  Video,
  Workflow,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@ayf/ui";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/videos", label: "Videos", icon: Video },
  { href: "/dashboard/agents", label: "Agents", icon: Sparkles },
  { href: "/dashboard/agents/tools", label: "Agent tools", icon: Wrench },
  { href: "/dashboard/agents/knowledge", label: "Knowledge", icon: BookOpen },
  { href: "/dashboard/agents/metrics", label: "Agent metrics", icon: Gauge },
  { href: "/dashboard/workflows", label: "Workflows", icon: Workflow },
  { href: "/dashboard/llm", label: "LLM", icon: BrainCircuit },
  { href: "/dashboard/llm/prompts", label: "Prompts", icon: FileText },
  { href: "/dashboard/llm/playground", label: "Playground", icon: MessagesSquare },
  { href: "/dashboard/llm/usage", label: "Usage & cost", icon: BarChart3 },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
] as const;

/** Persistent left navigation for the authenticated dashboard shell. */
export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-60 shrink-0 border-r border-border bg-card md:block">
      <div className="flex h-16 items-center gap-2 border-b border-border px-6">
        <Sparkles className="h-5 w-5 text-primary" />
        <span className="font-semibold">AI YT Factory</span>
      </div>
      <nav className="flex flex-col gap-1 p-3">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
