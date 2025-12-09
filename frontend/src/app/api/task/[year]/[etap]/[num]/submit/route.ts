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

    // Handle non-JSON error responses (e.g., 500 Internal Server Error)
    const contentType = response.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
      const text = await response.text();
      console.error("Submit proxy error: non-JSON response", response.status, text);
      return NextResponse.json(
        { success: false, error: "Wystąpił błąd serwera. Spróbuj ponownie." },
        { status: response.status }
      );
    }

    const data = await response.json();

    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    console.error("Submit proxy error:", error);
    return NextResponse.json(
      { success: false, error: "Nie udało się przesłać rozwiązania. Spróbuj ponownie." },
      { status: 500 }
    );
  }
}
