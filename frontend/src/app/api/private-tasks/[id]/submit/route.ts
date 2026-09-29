import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/api/proxy";

export const maxDuration = 180;

interface RouteParams {
  params: Promise<{ id: string }>;
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id } = await params;
  return proxyToBackend(request, `/api/private-tasks/${encodeURIComponent(id)}/submit`);
}
