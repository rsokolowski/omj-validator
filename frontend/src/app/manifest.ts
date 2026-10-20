import type { MetadataRoute } from "next";
import { APP_NAME } from "@/lib/utils/constants";

// Makes the site installable ("Do ekranu początkowego"). On iPhone that is
// required for Web Push - reminders about due wzorce (components/push).
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: APP_NAME,
    short_name: APP_NAME,
    description: "Przygotowanie do Olimpiady Matematycznej Juniorów",
    lang: "pl",
    start_url: "/wzorce",
    scope: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#2563eb",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
