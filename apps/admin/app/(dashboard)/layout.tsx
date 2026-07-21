import { ShieldCheck } from "lucide-react";

/** Admin dashboard shell. A full admin panel is built in a later phase. */
export default function AdminDashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex h-16 items-center gap-2 border-b border-border bg-card px-6">
        <ShieldCheck className="h-5 w-5 text-primary" />
        <span className="font-semibold">Admin Console</span>
      </header>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
