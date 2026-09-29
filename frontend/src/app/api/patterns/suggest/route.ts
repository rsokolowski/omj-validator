import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/api/proxy";

// Calls Gemini - allow for slow responses
export const maxDuration = 120;

export async function POST(request: NextRequest) {
  return proxyToBackend(request, "/api/patterns/suggest");
}
