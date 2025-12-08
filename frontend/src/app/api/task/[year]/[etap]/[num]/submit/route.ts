import { NextRequest, NextResponse } from "next/server";

const backendUrl = process.env.FASTAPI_URL || "http://localhost:8000";

// Increase timeout for AI processing (Gemini can take 60+ seconds)
export const maxDuration = 180;

interface RouteParams {
  params: Promise<{
    year: string;
    etap: string;
    num: string;
  }>;
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { year, etap, num } = await params;

  try {
    // Forward the form data to the backend
    const formData = await request.formData();

    // Forward cookies for authentication
    const cookie = request.headers.get("cookie");

    const response = await fetch(`${backendUrl}/task/${year}/${etap}/${num}/submit`, {
      method: "POST",
      body: formData,
      headers: cookie ? { cookie } : {},
    });

    const data = await response.json();

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("Submit proxy error:", error);
    return NextResponse.json(
      { error: "Failed to submit solution" },
      { status: 500 }
    );
  }
}
