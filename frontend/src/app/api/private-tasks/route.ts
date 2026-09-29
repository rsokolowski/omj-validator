import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/api/proxy";

// Creating tasks generates hints with AI - allow for slow responses
export const maxDuration = 180;

export async function GET(request: NextRequest) {
  return proxyToBackend(request, "/api/private-tasks");
}

export async function POST(request: NextRequest) {
  return proxyToBackend(request, "/api/private-tasks");
}
