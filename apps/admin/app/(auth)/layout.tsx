/** Minimal centered shell for admin authentication screens (placeholder). */
export default function AdminAuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm rounded-lg border border-border bg-card p-6 shadow-sm">
        {children}
      </div>
    </div>
  );
}
