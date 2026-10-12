import type { Metadata } from "next";
import { LoginForm } from "@/components/auth/LoginForm";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Zaloguj się",
  robots: { index: false, follow: false },
};

// Powroty z /auth/callback (backend) z ?error=
const ERROR_MESSAGES: Record<string, string> = {
  oauth_failed: "Nie udało się zalogować przez Google. Spróbuj jeszcze raz.",
  rate_limit_new_users:
    "Dziś założono już bardzo dużo kont, więc rejestracja jest chwilowo wstrzymana. Spróbuj jutro.",
  rate_limit_registrations_ip:
    "Z tej sieci (np. szkolnej) założono dziś już bardzo dużo kont, więc kolejne można będzie założyć jutro. Możesz też spróbować z innej sieci, np. w domu.",
  oauth_not_configured: "Logowanie przez Google jest teraz niedostępne. Zaloguj się loginem i hasłem.",
};

interface LoginPageProps {
  searchParams: Promise<{ next?: string | string[]; error?: string | string[] }>;
}

function one(value: string | string[] | undefined): string | undefined {
  return typeof value === "string" ? value : undefined;
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams;
  const rawNext = one(params.next);
  // Tylko zwykle sciezki tej strony; backend sprawdza to samo (safe_next_path),
  // tu odrzucamy wczesniej, zeby nie przenosic podejrzanego ?next= dalej
  const next =
    rawNext &&
    rawNext.startsWith("/") &&
    !rawNext.startsWith("//") &&
    !/[\\\u0000-\u001f]|%5c/i.test(rawNext)
      ? rawNext
      : undefined;
  const googleLoginUrl = next ? `/login/google?next=${encodeURIComponent(next)}` : "/login/google";
  const error = one(params.error);
  const errorMessage = error
    ? (ERROR_MESSAGES[error] ?? "Nie udało się zalogować. Spróbuj jeszcze raz.")
    : null;

  return <LoginForm googleLoginUrl={googleLoginUrl} next={next} errorMessage={errorMessage} />;
}
