import type { Metadata, Viewport } from "next";

import { ServiceWorkerRegistration } from "@/components/service-worker";

import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "AI YouTube Factory",
    template: "%s · AI YouTube Factory",
  },
  description:
    "Autonomously research, generate, edit, optimize, publish, and improve YouTube content with AI.",
  applicationName: "AI YouTube Factory",
  appleWebApp: {
    capable: true,
    title: "AYF",
    // "default" keeps the status bar legible in both themes; "black-translucent"
    // draws content under it, which crops the header on a notched phone.
    statusBarStyle: "default",
  },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Zoom is left enabled on purpose. Blocking it is a WCAG failure and the
  // usual reason a form is unusable for anyone who needs to magnify it.
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1120" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen font-sans antialiased">
        <Providers>{children}</Providers>
        <ServiceWorkerRegistration />
      </body>
    </html>
  );
}
