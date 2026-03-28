import type { Metadata } from "next";
import { Box } from "@mui/material";
import { serverFetch } from "@/lib/api/server";
import { ProgressData, User } from "@/lib/types";
import { PageHeader } from "@/components/layout/PageHeader";
import { MockEtap2Section } from "@/components/practice/MockEtap2Section";
import { LoginPrompt } from "@/components/common/LoginPrompt";

export const metadata: Metadata = {
  title: "Próbny Etap 2",
  description:
    "Sprawdź się w warunkach zbliżonych do prawdziwego Etapu 2 Olimpiady Matematycznej Juniorów. Zestawy 5 zadań z limitem czasowym 3 godzin.",
  alternates: { canonical: "/practice/etap2" },
};

export const dynamic = "force-dynamic";

interface ProgressResponse extends ProgressData {
  user: User | null;
  is_authenticated: boolean;
}

async function getProgressData(): Promise<ProgressResponse> {
  return serverFetch<ProgressResponse>("/api/progress/data");
}

export default async function MockEtap2Page() {
  const data = await getProgressData();

  return (
    <Box>
      <PageHeader
        title="Próbny Etap 2"
        subtitle="Sprawdź się w warunkach zbliżonych do prawdziwego konkursu"
      />

      {data.is_authenticated ? (
        <MockEtap2Section nodes={data.nodes} />
      ) : (
        <LoginPrompt redirectUrl="/practice/etap2" />
      )}
    </Box>
  );
}
