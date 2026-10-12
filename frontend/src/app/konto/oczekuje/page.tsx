import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Alert } from "@mui/material";
import { PendingAccount } from "@/components/account/PendingAccount";
import { getAuthMe } from "@/lib/api/serverAccount";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Czekamy na zgodę rodzica",
  robots: { index: false, follow: false },
};

export default async function PendingAccountPage() {
  const auth = await getAuthMe();
  if (!auth) {
    return <Alert severity="error">Nie udało się załadować strony. Spróbuj za chwilę.</Alert>;
  }
  if (!auth.is_authenticated) {
    redirect("/login");
  }
  if (auth.account?.needs_profile) {
    redirect("/konto/uzupelnij");
  }
  return <PendingAccount initial={auth} />;
}
