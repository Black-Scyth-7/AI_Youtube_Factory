import { MobileNav } from "@/components/mobile-nav";
import { Sidebar } from "@/components/sidebar";
import { TopNav } from "@/components/top-nav";

/**
 * Authenticated dashboard shell: persistent sidebar + top navigation with a
 * scrollable content region. Auth gating is added in a later phase.
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col">
        <TopNav />
        {/* pb-20 keeps content clear of the fixed mobile bar. */}
        <main className="flex-1 overflow-y-auto p-4 pb-20 md:p-6 md:pb-6">
          {children}
        </main>
        <MobileNav />
      </div>
    </div>
  );
}
