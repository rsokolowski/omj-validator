// Account API: registration, login, age step, pending screen, parent pages,
// password reset. Errors are APIError with `code` / `field` / `retryAfter`.

import { APIError, fetchAPI } from "@/lib/api/client";
import type {
  ConsentDecisionResponse,
  ConsentView,
  GoogleRegistrationResponse,
  LoginAvailableResponse,
  ParentChildrenResponse,
  ParentDeleteResponse,
  PasswordResetCheckResponse,
  RedirectResponse,
  RegistrationStateResponse,
  ResendResponse,
} from "@/lib/types";

const NETWORK_ERROR = "Brak połączenia z serwerem. Sprawdź internet i spróbuj ponownie.";

/** A message for an Alert: the API's Polish `detail`, or a calm network error. */
export function errorText(error: unknown): string {
  if (error instanceof APIError) {
    if (error.status === 0) return NETWORK_ERROR;
    if (error.status >= 500 && error.status !== 502) {
      return "Coś poszło nie tak po naszej stronie. Spróbuj za chwilę.";
    }
    return error.message || "Coś poszło nie tak. Spróbuj ponownie.";
  }
  return NETWORK_ERROR;
}

function post<T>(endpoint: string, body: unknown): Promise<T> {
  return fetchAPI<T>(endpoint, { method: "POST", body: JSON.stringify(body) });
}

export interface AgeAnswers {
  birth_year: number;
  turned_16?: boolean;
}

export const accountApi = {
  login: (body: { login: string; password: string; remember: boolean; next?: string }) =>
    post<RedirectResponse>("/api/auth/login", body),

  loginAvailable: (login: string) =>
    fetchAPI<LoginAvailableResponse>(`/api/auth/login-available?login=${encodeURIComponent(login)}`),

  registrationState: () => fetchAPI<RegistrationStateResponse>("/api/auth/register/state"),

  registerLogin: (
    body: AgeAnswers & { login: string; password: string; parent_email: string }
  ) => post<RedirectResponse>("/api/auth/register/login", body),

  registerGoogle: (body: AgeAnswers & { parent_email?: string; accept_terms?: boolean }) =>
    post<GoogleRegistrationResponse>("/api/auth/register/google", body),

  completeProfile: (body: AgeAnswers & { parent_email?: string; accept_terms?: boolean }) =>
    post<RedirectResponse>("/api/auth/profile", body),

  resendConsent: () => post<ResendResponse>("/api/account/consent/resend", {}),

  changeParentEmail: (parent_email: string) =>
    post<ResendResponse>("/api/account/parent-email", { parent_email }),

  passwordResetRequest: (login: string) =>
    post<{ sent: true }>("/api/auth/password-reset/request", { login }),

  passwordResetCheck: (token: string) =>
    fetchAPI<PasswordResetCheckResponse>(
      `/api/auth/password-reset/check?t=${encodeURIComponent(token)}`
    ),

  passwordResetConfirm: (token: string, password: string) =>
    post<{ ok: true }>("/api/auth/password-reset/confirm", { token, password }),
};

export const parentApi = {
  consent: (token: string) =>
    fetchAPI<ConsentView>(`/api/parent/consent?t=${encodeURIComponent(token)}`),

  decide: (token: string, decision: "accept" | "decline") =>
    post<ConsentDecisionResponse>("/api/parent/consent", { token, decision }),

  resendConsent: (token: string) => post<{ sent: true }>("/api/parent/consent/resend", { token }),

  children: (token: string) =>
    fetchAPI<ParentChildrenResponse>(`/api/parent/children?t=${encodeURIComponent(token)}`),

  deleteChild: (token: string, childId: string) =>
    post<ParentDeleteResponse>(`/api/parent/children/${encodeURIComponent(childId)}/delete`, {
      token,
    }),

  setPassword: (token: string, childId: string, password: string) =>
    post<{ ok: true }>(`/api/parent/children/${encodeURIComponent(childId)}/password`, {
      token,
      password,
    }),

  requestLink: (email: string) => post<{ sent: true }>("/api/parent/request-link", { email }),
};
