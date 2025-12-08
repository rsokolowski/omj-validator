import type { NextConfig } from "next";

// Backend URL - uses environment variable in production, localhost in development
const backendUrl = process.env.FASTAPI_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  // Proxy API requests to FastAPI backend
  // Use afterFiles so Next.js API routes are checked first
  async rewrites() {
    return {
      afterFiles: [
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
