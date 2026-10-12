"use client";

import useSWR from "swr";
import { AuthMeResponse } from "@/lib/types";
import { fetchAPI } from "@/lib/api/client";

const fetcher = (url: string) => fetchAPI<AuthMeResponse>(url);

export const AUTH_ME_KEY = "/api/auth/me";

interface UseAuthOptions {
  /** Refetch when the tab regains focus (account gate, pending screen) */
  revalidateOnFocus?: boolean;
  /** Poll every N ms (pending screen waits for the parent); a function decides from the latest answer */
  refreshInterval?: number | ((latest?: AuthMeResponse) => number);
  /** Server-rendered answer to start from (no loading flash) */
  fallbackData?: AuthMeResponse;
}

export function useAuth(options: UseAuthOptions = {}) {
  const { data, error, isLoading, mutate } = useSWR(AUTH_ME_KEY, fetcher, {
    revalidateOnFocus: options.revalidateOnFocus ?? false,
    refreshInterval: options.refreshInterval ?? 0,
    shouldRetryOnError: false,
    fallbackData: options.fallbackData,
  });

  const account = data?.account ?? null;
  return {
    user: data?.user ?? null,
    account,
    isAuthenticated: data?.is_authenticated ?? false,
    isGroupMember: data?.user?.is_group_member ?? false,
    isAdmin: data?.is_admin ?? false,
    needsProfile: account?.needs_profile ?? false,
    isPendingParent: account?.status === "pending_parent",
    data,
    isLoading,
    error,
    refetch: mutate,
  };
}
