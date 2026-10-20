import type { NextConfig } from "next";

// Backend URL - uses environment variable in production, localhost in development
const backendUrl = process.env.FASTAPI_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  // Enable standalone output for Docker deployment
  output: "standalone",
  // Pages opened from e-mail links carry a token in ?t= until the page hides
  // it: never send their URL to anyone in a Referer (the pages also set
  // <meta name="referrer" content="no-referrer">)
  async headers() {
    return [
      ...["/rodzic", "/rodzic/:path*", "/reset-hasla/:path*"].map((source) => ({
        source,
        headers: [{ key: "Referrer-Policy", value: "no-referrer" }],
      })),
      // The service worker (reminders) must never be served stale from a cache
      { source: "/sw.js", headers: [{ key: "Cache-Control", value: "no-cache, no-store, must-revalidate" }] },
    ];
  },
  // Proxy API requests to FastAPI backend
  // Use fallback so Next.js API routes and pages are checked first
  async rewrites() {
    return {
      fallback: [
        {
          source: "/api/:path*",
          destination: `${backendUrl}/api/:path*`,
        },
        {
          source: "/login/:path*",
          destination: `${backendUrl}/login/:path*`,
        },
        {
          source: "/auth/:path*",
          destination: `${backendUrl}/auth/:path*`,
        },
        {
          source: "/logout",
          destination: `${backendUrl}/logout`,
        },
        {
          source: "/pdf/:path*",
          destination: `${backendUrl}/pdf/:path*`,
        },
        {
          source: "/uploads/:path*",
          destination: `${backendUrl}/uploads/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
