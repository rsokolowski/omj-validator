import { Box } from "@mui/material";
import { serverFetch } from "@/lib/api/server";
import { ProgressData, User } from "@/lib/types";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProgressStats } from "@/components/progress/ProgressStats";
import { CategoryFilter } from "@/components/progress/CategoryFilter";
import { RecommendationsList } from "@/components/progress/RecommendationsList";
import { LoginPrompt } from "@/components/common/LoginPrompt";

export const dynamic = "force-dynamic";

interface ProgressPageProps {
  searchParams: Promise<{ category?: string }>;
}

interface ProgressResponse extends ProgressData {
  user: User | null;
  is_authenticated: boolean;
}

async function getProgressData(category?: string): Promise<ProgressResponse> {
  const url = category ? `/api/progress/data?category=${category}` : "/api/progress/data";
  return serverFetch<ProgressResponse>(url);
}

export default async function ProgressPage({ searchParams }: ProgressPageProps) {
  const { category } = await searchParams;
  const data = await getProgressData(category);

  return (
    <Box>
      <PageHeader
        title="Nauka"
        subtitle="Śledź swój rozwój i odkrywaj rekomendowane zadania"
      />

      {/* Stats */}
      <ProgressStats stats={data.stats} />

      {/* Category Filter */}
      <CategoryFilter currentCategory={category} />

      {/* Recommendations or Login Prompt */}
      {data.is_authenticated ? (
        data.recommendations.length > 0 && (
          <RecommendationsList recommendations={data.recommendations} />
        )
      ) : (
        <LoginPrompt redirectUrl="/progress" />
      )}
    </Box>
  );
}
