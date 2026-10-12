import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { RegistrationWizard } from "@/components/account/RegistrationWizard";
import { getAuthMe, homeFor, one } from "@/lib/api/serverAccount";
import { warsawYear } from "@/lib/utils/account";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Załóż konto",
  robots: { index: false, follow: false },
};

interface PageProps {
  searchParams: Promise<{ google?: string | string[]; blad?: string | string[] }>;
}

export default async function RegistrationPage({ searchParams }: PageProps) {
  const params = await searchParams;
  const auth = await getAuthMe();
  // Kto ma juz konto, nie zaklada drugiego
  if (auth?.is_authenticated && auth.account) {
    redirect(homeFor(auth.account));
  }

  return (
    <RegistrationWizard
      currentYear={warsawYear()}
      googleMode={one(params.google) === "1"}
      sameAddressError={one(params.blad) === "ten-sam-adres"}
    />
  );
}
