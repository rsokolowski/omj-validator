import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Alert } from "@mui/material";
import { CompleteProfile } from "@/components/account/CompleteProfile";
import { getAuthMe, homeFor } from "@/lib/api/serverAccount";
import { warsawYear } from "@/lib/utils/account";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Uzupełnij konto",
  robots: { index: false, follow: false },
};

export default async function CompleteProfilePage() {
  const auth = await getAuthMe();
  if (!auth) {
    return <Alert severity="error">Nie udało się załadować strony. Spróbuj za chwilę.</Alert>;
  }
  if (!auth.is_authenticated) {
    redirect("/login");
  }
  if (!auth.account?.needs_profile) {
    redirect(homeFor(auth.account));
  }
  return <CompleteProfile currentYear={warsawYear()} ownEmail={auth.user?.email ?? null} />;
}
