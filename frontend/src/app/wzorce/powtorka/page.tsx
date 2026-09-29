import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Box } from "@mui/material";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { PageHeader } from "@/components/layout/PageHeader";
import { ReviewSession } from "@/components/patterns/ReviewSession";
import { serverFetch } from "@/lib/api/server";
import { User } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Powtórka wzorców",
  robots: { index: false, follow: false },
};

export default async function ReviewPage() {
  const auth = await serverFetch<{ user: User | null; is_authenticated: boolean }>("/api/auth/me");
  if (!auth.is_authenticated) {
    redirect("/login?next=/wzorce/powtorka");
  }
  return (
    <Box>
      <PageHeader title="Powtórka wzorców" subtitle="Najpierw przypomnij sobie sam, potem porównaj.">
        <Breadcrumb items={[{ label: "Wzorce", href: "/wzorce" }, { label: "Powtórka" }]} />
      </PageHeader>
      <ReviewSession />
    </Box>
  );
}
