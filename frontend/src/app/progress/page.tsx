import { Box, Typography } from "@mui/material";
import { serverFetch } from "@/lib/api/server";
import { ProgressData, User } from "@/lib/types";
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
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" sx={{ fontWeight: 700, color: "grey.900", mb: 1 }}>
          Nauka
        </Typography>
        <Typography color="text.secondary">
          Śledź swój rozwój i odkrywaj rekomendowane zadania
        </Typography>
      </Box>

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
