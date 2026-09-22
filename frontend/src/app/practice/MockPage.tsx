import { Box } from "@mui/material";
import { serverFetch } from "@/lib/api/server";
import { ProgressData, User } from "@/lib/types";
import { PageHeader } from "@/components/layout/PageHeader";
import { MockSection } from "@/components/practice/MockSection";
import { LoginPrompt } from "@/components/common/LoginPrompt";
import { MockEtap, MOCK_ETAP_CONFIG } from "@/lib/utils/constants";

interface ProgressResponse extends ProgressData {
  user: User | null;
  is_authenticated: boolean;
}

/**
 * Shared body of /practice/etap1 and /practice/etap2 - the two routes differ
 * only in their metadata and in which mock etap they render.
 */
export async function MockPage({ etap }: { etap: MockEtap }) {
  const config = MOCK_ETAP_CONFIG[etap];
  const data = await serverFetch<ProgressResponse>("/api/progress/data");

  return (
    <Box>
      <PageHeader
        title={config.label}
        subtitle="Sprawdź się w warunkach zbliżonych do prawdziwego konkursu"
      />

      {data.is_authenticated ? (
        <MockSection etap={etap} nodes={data.nodes} />
      ) : (
        <LoginPrompt redirectUrl={config.path} />
      )}
    </Box>
  );
}
