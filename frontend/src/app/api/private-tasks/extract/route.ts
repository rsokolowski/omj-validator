import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/api/proxy";

// Reading a task off a photo is an AI call - allow for slow responses
export const maxDuration = 180;

export async function POST(request: NextRequest) {
  return proxyToBackend(request, "/api/private-tasks/extract");
}
