"use client";

import useSWR from "swr";
import { User } from "@/lib/types";
import { fetchAPI } from "@/lib/api/client";

interface AuthResponse {
  user: User | null;
  is_authenticated: boolean;
  is_admin: boolean;
}

const fetcher = (url: string) => fetchAPI<AuthResponse>(url);

export function useAuth() {
  const { data, error, isLoading, mutate } = useSWR("/api/auth/me", fetcher, {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });

  return {
    user: data?.user ?? null,
    isAuthenticated: data?.is_authenticated ?? false,
    isGroupMember: data?.user?.is_group_member ?? false,
    isAdmin: data?.is_admin ?? false,
    isLoading,
    error,
    refetch: mutate,
  };
}
