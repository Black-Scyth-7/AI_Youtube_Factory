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
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
