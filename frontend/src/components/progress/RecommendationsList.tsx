import Link from "next/link";
import { Box, Paper, Typography, Chip } from "@mui/material";
import { GraphNode } from "@/lib/types";
import { DifficultyStars } from "@/components/ui/DifficultyStars";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { MathContent } from "@/components/ui/MathContent";
import { ETAP_NAMES } from "@/lib/utils/constants";

interface RecommendationsListProps {
  recommendations: GraphNode[];
}

export function RecommendationsList({ recommendations }: RecommendationsListProps) {
  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}>
        Polecane zadania
      </Typography>
      <Typography variant="body2" sx={{ color: "grey.600", mb: 2 }}>
        Na podstawie Twoich postępów, rekomendujemy następne zadania do rozwiązania:
      </Typography>

      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
        {recommendations.slice(0, 5).map((task) => (
          <Link
            key={task.key}
            href={`/task/${task.year}/${task.etap}/${task.number}`}
            style={{ textDecoration: "none" }}
          >
            <Box
              sx={{
                p: 2,
                border: 1,
                borderColor: "grey.200",
                borderRadius: 1,
                transition: "all 0.15s ease",
                "&:hover": {
                  borderColor: "primary.main",
                  bgcolor: "grey.50",
                },
              }}
            >
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 1 }}>
                <Box>
                  <Typography variant="subtitle2" sx={{ color: "grey.800", fontWeight: 600 }}>
                    Zadanie {task.number}
                  </Typography>
                  <Typography variant="caption" sx={{ color: "grey.500" }}>
                    {task.year} • {ETAP_NAMES[task.etap] || task.etap}
                  </Typography>
                </Box>
                {task.difficulty && <DifficultyStars difficulty={task.difficulty} />}
              </Box>

              <Box sx={{ color: "grey.600", mb: 1.5 }}>
                <MathContent content={task.title} />
              </Box>

              <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                {task.categories.map((cat) => (
                  <CategoryBadge key={cat} category={cat} size="small" />
                ))}
              </Box>
            </Box>
          </Link>
        ))}
      </Box>
    </Paper>
  );
}
