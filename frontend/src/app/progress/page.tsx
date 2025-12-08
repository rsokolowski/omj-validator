import { Box, Typography } from "@mui/material";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { serverFetch } from "@/lib/api/server";
import { ProgressData, User } from "@/lib/types";
import { ProgressStats } from "@/components/progress/ProgressStats";
import { CategoryFilter } from "@/components/progress/CategoryFilter";
import { RecommendationsList } from "@/components/progress/RecommendationsList";

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

  const breadcrumbItems = [
    { label: "Lata", href: "/years" },
    { label: "Nauka" },
  ];

  return (
    <Box>
      <Breadcrumb items={breadcrumbItems} />

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

      {/* Recommendations */}
      {data.recommendations.length > 0 && (
        <RecommendationsList recommendations={data.recommendations} />
      )}
    </Box>
  );
}
