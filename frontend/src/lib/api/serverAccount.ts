// Server Components only: who is signed in and where their account stands.

import { serverFetch } from "@/lib/api/server";
import type { AccountInfo, AuthMeResponse } from "@/lib/types";

/** /api/auth/me, or null when the backend cannot be reached (render, don't crash). */
export async function getAuthMe(): Promise<AuthMeResponse | null> {
  try {
    return await serverFetch<AuthMeResponse>("/api/auth/me");
  } catch {
    return null;
  }
}

/** Where a signed-in account belongs (mirrors _home_for in app/accounts/routes.py). */
export function homeFor(account: AccountInfo | null): string {
  if (account?.needs_profile) return "/konto/uzupelnij";
  if (account?.status === "pending_parent") return "/konto/oczekuje";
  return "/years";
}

/** Single value of a search param. */
export function one(value: string | string[] | undefined): string | undefined {
  return typeof value === "string" ? value : undefined;
}
