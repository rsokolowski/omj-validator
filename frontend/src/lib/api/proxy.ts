// Server-side proxy for FastAPI endpoints that need a longer timeout than the
// next.config.ts rewrites give them (AI calls can take a minute or more).

import { NextRequest, NextResponse } from "next/server";

const backendUrl = process.env.FASTAPI_URL || "http://localhost:8000";

/**
 * Forward the request as-is (method, raw body with its content type, cookies,
 * query string) to the same path on the backend and relay the JSON answer,
 * including status and rate-limit headers.
 */
export async function proxyToBackend(request: NextRequest, path: string): Promise<NextResponse> {
  const headers: Record<string, string> = {};
  const cookie = request.headers.get("cookie");
  if (cookie) headers.cookie = cookie;
  const contentType = request.headers.get("content-type");
  if (contentType) headers["content-type"] = contentType;

  const hasBody = request.method !== "GET" && request.method !== "HEAD";

  try {
    const response = await fetch(`${backendUrl}${path}${request.nextUrl.search}`, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      cache: "no-store",
    });

    const passHeaders = new Headers();
    for (const name of ["retry-after", "x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset"]) {
      const value = response.headers.get(name);
      if (value) passHeaders.set(name, value);
    }

    const responseType = response.headers.get("content-type");
    if (!responseType || !responseType.includes("application/json")) {
      console.error("Proxy error: non-JSON response", path, response.status);
      return NextResponse.json(
        { detail: "Wystąpił błąd serwera. Spróbuj ponownie." },
        { status: response.status >= 400 ? response.status : 502, headers: passHeaders }
      );
    }

    const data = await response.json();
    return NextResponse.json(data, { status: response.status, headers: passHeaders });
  } catch (error) {
    console.error("Proxy error:", path, error);
    return NextResponse.json(
      { detail: "Nie udało się połączyć z serwerem. Spróbuj ponownie." },
      { status: 502 }
    );
  }
}
