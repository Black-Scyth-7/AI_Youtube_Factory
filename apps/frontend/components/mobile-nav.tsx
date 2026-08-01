"use client";

import {
  BrainCircuit,
  CreditCard,
  LayoutDashboard,
  Menu,
  Sparkles,
  Video,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { cn } from "@ayf/ui";

import { NAV_ITEMS } from "@/components/nav-items";

/**
 * The five destinations that fit across a phone. Everything else lives behind
 * "More", which opens the full list.
 */
const PRIMARY = [
  { href: "/dashboard", label: "Home", icon: LayoutDashboard },
  { href: "/dashboard/videos", label: "Videos", icon: Video },
  { href: "/dashboard/agents", label: "Agents", icon: Sparkles },
  { href: "/dashboard/llm", label: "LLM", icon: BrainCircuit },
  { href: "/dashboard/billing", label: "Billing", icon: CreditCard },
] as const;

/**
 * Navigation for small screens.
 *
 * The sidebar is `hidden md:block`, so below that breakpoint the dashboard had
 * no navigation at all — every page was reachable only by typing its URL. This
 * is a bottom bar because a phone is held at the bottom, plus a sheet for the
 * destinations that do not fit.
 */
export function MobileNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Navigating must dismiss the sheet, or it stays over the page the user
  // just asked for.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  // A fixed overlay that scrolls the page behind it is disorienting, and on
  // iOS the background scrolls instead of the sheet.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-background/95 backdrop-blur md:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation"
        >
          <div className="flex h-16 items-center justify-between border-b border-border px-4">
            <span className="font-semibold">Menu</span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close navigation"
              className="rounded-md p-2 text-muted-foreground hover:bg-accent"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
          <nav className="flex max-h-[calc(100vh-4rem)] flex-col gap-1 overflow-y-auto p-3 pb-24">
            {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-3 text-sm",
                  pathname === href
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-accent",
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            ))}
          </nav>
        </div>
      )}

      <nav
        aria-label="Primary"
        className={cn(
          "fixed inset-x-0 bottom-0 z-50 flex border-t border-border bg-card md:hidden",
          // Keeps the bar clear of the home indicator on a notched phone.
          "pb-[env(safe-area-inset-bottom)]",
        )}
      >
        {PRIMARY.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex flex-1 flex-col items-center gap-1 py-2 text-[11px]",
                // 44px is the minimum comfortable touch target.
                "min-h-11 justify-center",
                active ? "text-primary" : "text-muted-foreground",
              )}
            >
              <Icon className="h-5 w-5" />
              {label}
            </Link>
          );
        })}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label="More navigation"
          className={cn(
            "flex min-h-11 flex-1 flex-col items-center justify-center gap-1 py-2 text-[11px]",
            open ? "text-primary" : "text-muted-foreground",
          )}
        >
          <Menu className="h-5 w-5" />
          More
        </button>
      </nav>
    </>
  );
}
