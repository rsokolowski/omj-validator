// API client for communicating with FastAPI backend (client-side)

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "APIError";
  }
}

/**
 * Human-readable message from a FastAPI error body. Validation errors (422)
 * arrive as a list of objects in English - never show those raw.
 */
function errorMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const { detail, error } = body as { detail?: unknown; error?: unknown };
    if (typeof error === "string") return error;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return "Nieprawidłowe dane. Sprawdź wypełnione pola.";
  }
  return fallback;
}

export async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const res = await fetch(url, {
    ...options,
    credentials: "include", // Forward cookies for session auth
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new APIError(res.status, errorMessage(body, res.statusText || "Wystąpił błąd"));
  }

  return res.json();
}


// File upload helper
export async function uploadFiles<T>(
  endpoint: string,
  files: File[],
  onProgress?: (progress: number) => void,
  fields?: Record<string, string>
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const formData = new FormData();
  files.forEach((file) => formData.append("images", file));
  Object.entries(fields ?? {}).forEach(([name, value]) => formData.append(name, value));

  // Use XMLHttpRequest for progress tracking
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        const progress = Math.round((e.loaded * 100) / e.total);
        onProgress(progress);
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        // Parse JSON error response to get the actual error message
        let message = xhr.statusText;
        try {
          message = errorMessage(JSON.parse(xhr.responseText), xhr.statusText);
        } catch {
          // If response isn't JSON, use status text
        }
        reject(new APIError(xhr.status, message));
      }
    });

    xhr.addEventListener("error", () => {
      reject(new APIError(0, "Network error"));
    });

    xhr.open("POST", url);
    xhr.withCredentials = true;
    xhr.send(formData);
  });
}
