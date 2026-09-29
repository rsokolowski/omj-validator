import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/api/proxy";

// Calls Gemini - allow for slow responses
export const maxDuration = 120;

interface RouteParams {
  params: Promise<{ id: string }>;
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id } = await params;
  return proxyToBackend(request, `/api/patterns/${encodeURIComponent(id)}/suggest-links`);
}
