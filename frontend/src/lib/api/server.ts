// API client for server-side fetching (Server Components only)
// This file uses next/headers which only works in Server Components

import { cookies } from "next/headers";

export class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "APIError";
  }
}

export async function serverFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  // When running on server, we need to use the full backend URL
  const backendUrl = process.env.FASTAPI_URL || "http://localhost:8000";
  const url = `${backendUrl}${endpoint}`;

  // Forward cookies from the incoming request for authentication
  const cookieStore = await cookies();
  const cookieHeader = cookieStore.toString();

  const res = await fetch(url, {
    ...options,
    cache: "no-store", // Don't cache by default for dynamic data
    headers: {
      "Content-Type": "application/json",
      ...(cookieHeader && { Cookie: cookieHeader }),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new APIError(res.status, error.detail || res.statusText);
  }

  return res.json();
}
