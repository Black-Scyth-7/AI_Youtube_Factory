import type { MetadataRoute } from "next";

/**
 * Web app manifest, which is what makes the dashboard installable on a phone.
 *
 * A route rather than a static file so the values stay in TypeScript and are
 * checked against Next's type for them.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "AI YouTube Factory",
    short_name: "AYF",
    description:
      "Research, generate, publish, and analyse YouTube content with AI.",
    // Installs open straight into the dashboard; the marketing page is not
    // what someone who installed the app is looking for.
    start_url: "/dashboard",
    scope: "/",
    display: "standalone",
    orientation: "portrait-primary",
    background_color: "#0b1120",
    theme_color: "#2563eb",
    categories: ["productivity", "business"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      {
        // Android crops icons to its own shape; a maskable one keeps the mark
        // inside the safe area instead of having its corners clipped off.
        src: "/icons/maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
