// API client for communicating with FastAPI backend (client-side)

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export class APIError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "APIError";
  }
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
    const error = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new APIError(res.status, error.detail || res.statusText);
  }

  return res.json();
}


// File upload helper
export async function uploadFiles<T>(
  endpoint: string,
  files: File[],
  onProgress?: (progress: number) => void
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const formData = new FormData();
  files.forEach((file) => formData.append("images", file));

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
        let errorMessage = xhr.statusText;
        try {
          const errorData = JSON.parse(xhr.responseText);
          errorMessage = errorData.error || errorData.detail || xhr.statusText;
        } catch {
          // If response isn't JSON, use status text
        }
        reject(new APIError(xhr.status, errorMessage));
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
