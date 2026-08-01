import {
  BarChart3,
  BookOpen,
  BrainCircuit,
  CreditCard,
  FileText,
  Gauge,
  LayoutDashboard,
  MessagesSquare,
  Plug,
  Settings,
  Sparkles,
  Video,
  Workflow,
  Wrench,
} from "lucide-react";

/**
 * The dashboard's navigation, in one place.
 *
 * The sidebar and the mobile menu both render this. Two copies drifted apart
 * the moment a page was added to one and not the other — which is how the
 * billing console shipped with no way to reach it.
 */
export const NAV_ITEMS = [
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
  { href: "/dashboard/billing", label: "Billing", icon: CreditCard },
  { href: "/dashboard/plugins", label: "Plugins", icon: Plug },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
] as const;
