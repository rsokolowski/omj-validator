"use client";

import Link from "next/link";
import { Card, CardContent, Box, Typography, Chip } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { DifficultyStars } from "@/components/ui/DifficultyStars";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { TaskWithStats } from "@/lib/types";
import { getMaxScore } from "@/lib/utils/constants";

interface TaskCardProps {
  task: TaskWithStats;
  year: string;
  etap: string;
  showStats?: boolean;
}

export function TaskCard({ task, year, etap, showStats = false }: TaskCardProps) {
  const href = `/task/${year}/${etap}/${task.number}`;

  return (
    <Link href={href} style={{ textDecoration: "none" }}>
      <Card
        sx={{
          transition: "all 0.15s ease",
          "&:hover": {
            transform: "translateY(-2px)",
            boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
          },
        }}
      >
        <CardContent sx={{ p: 2.5 }}>
          {/* Header */}
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
            <Typography
              sx={{
                fontWeight: 600,
                color: "primary.main",
              }}
            >
              Zadanie {task.number}
            </Typography>
            {showStats && task.submission_count > 0 && (
              <Chip
                label={`${task.submission_count} ${getProbyText(task.submission_count)}`}
                size="small"
                sx={{
                  height: 22,
                  fontSize: "0.75rem",
                  bgcolor: "grey.100",
                  color: "grey.600",
                }}
              />
            )}
          </Box>

          {/* Title */}
          <Box sx={{ mb: 1, color: "grey.700" }}>
            <MathContent content={task.title} />
          </Box>

          {/* Meta row: difficulty and categories */}
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mb: 1 }}>
            {task.difficulty && (
              <DifficultyStars difficulty={task.difficulty} size="small" />
            )}
            {task.categories.map((cat) => (
              <CategoryBadge key={cat} category={cat} size="small" />
            ))}
          </Box>

          {/* Stats */}
          {showStats && task.highest_score !== null && task.highest_score > 0 && (
            <Box sx={{ mt: 1.5, display: "flex", gap: 2 }}>
              <Typography variant="body2" color="text.secondary">
                Najwyższy wynik:{" "}
                <Box
                  component="span"
                  className={`score-${task.highest_score}`}
                  sx={{ fontWeight: 600 }}
                >
                  {task.highest_score}/{getMaxScore(etap)}
                </Box>
              </Typography>
            </Box>
          )}

          {showStats && task.submission_count === 0 && (
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ mt: 1, fontStyle: "italic" }}
            >
              Brak prób
            </Typography>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}

function getProbyText(count: number): string {
  if (count === 1) return "próba";
  if (count >= 2 && count <= 4) return "próby";
  return "prób";
}
