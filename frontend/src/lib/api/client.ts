// API client for communicating with FastAPI backend (client-side)

import type { AiConfigResponse, AiConfigUpdateResponse, AiProviderId } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/** Error body of the JSON API: `detail` plus optional machine-readable extras */
export interface APIErrorBody {
  detail?: unknown;
  /** e.g. "invalid", "email_cooldown", "parent_consent_pending" */
  code?: unknown;
  /** Form field the error belongs to, e.g. "parent_email" */
  field?: unknown;
  /** Seconds until the action may be retried (429) */
  retry_after?: unknown;
  /** Link state on 410/404 answers of the e-mail link endpoints */
  state?: unknown;
  redirect?: unknown;
  [key: string]: unknown;
}

export class APIError extends Error {
  constructor(
    public status: number,
    message: string,
    public body: APIErrorBody | null = null
  ) {
    super(message);
    this.name = "APIError";
  }

  get code(): string | undefined {
    return typeof this.body?.code === "string" ? this.body.code : undefined;
  }

  get field(): string | undefined {
    return typeof this.body?.field === "string" ? this.body.field : undefined;
  }

  get retryAfter(): number | undefined {
    return typeof this.body?.retry_after === "number" ? this.body.retry_after : undefined;
  }

  get state(): string | undefined {
    return typeof this.body?.state === "string" ? this.body.state : undefined;
  }
}

function asBody(body: unknown): APIErrorBody | null {
  return body && typeof body === "object" && !Array.isArray(body) ? (body as APIErrorBody) : null;
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
    throw new APIError(
      res.status,
      errorMessage(body, res.statusText || "Wystąpił błąd"),
      asBody(body)
    );
  }

  return res.json();
}


// Admin: AI provider/model switch
export function getAiConfig(): Promise<AiConfigResponse> {
  return fetchAPI<AiConfigResponse>("/api/admin/ai-config");
}

/** Pings the model server-side before storing; rejects with APIError (400/409/502) */
export function putAiConfig(provider: AiProviderId, model: string): Promise<AiConfigUpdateResponse> {
  return fetchAPI<AiConfigUpdateResponse>("/api/admin/ai-config", {
    method: "PUT",
    body: JSON.stringify({ provider, model }),
  });
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
        let body: APIErrorBody | null = null;
        try {
          const parsed = JSON.parse(xhr.responseText);
          message = errorMessage(parsed, xhr.statusText);
          body = asBody(parsed);
        } catch {
          // If response isn't JSON, use status text
        }
        reject(new APIError(xhr.status, message, body));
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
