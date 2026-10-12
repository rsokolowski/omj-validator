import type { Metadata } from "next";
import { PasswordResetConfirm } from "@/components/auth/PasswordResetConfirm";
import { one } from "@/lib/api/serverAccount";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Nowe hasło",
  robots: { index: false, follow: false },
  // Token jest w adresie - nie wysylamy go dalej w naglowku Referer
  referrer: "no-referrer",
};

interface PageProps {
  searchParams: Promise<{ t?: string | string[] }>;
}

export default async function PasswordResetConfirmPage({ searchParams }: PageProps) {
  const params = await searchParams;
  return <PasswordResetConfirm token={one(params.t) || null} />;
}
