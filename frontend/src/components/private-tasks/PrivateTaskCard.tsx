import Link from "next/link";
import { Box, Chip, Paper, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { DifficultyStars } from "@/components/ui/DifficultyStars";
import { PrivateTaskSummary } from "@/lib/types";
import { formatDate } from "@/lib/utils/dates";

function scoreColors(score: number) {
  if (score >= 5) return { bg: "#dcfce7", color: "#166534", border: "#86efac" };
  if (score >= 2) return { bg: "#fef3c7", color: "#92400e", border: "#fcd34d" };
  return { bg: "#fee2e2", color: "#991b1b", border: "#fca5a5" };
}

export function PrivateTaskCard({ task }: { task: PrivateTaskSummary }) {
  const colors = task.best_score !== null ? scoreColors(task.best_score) : null;
  return (
    <Paper
      component="article"
      sx={{ p: 2.5, display: "flex", flexDirection: "column", gap: 1, height: "100%" }}
    >
      <Link href={`/moje-zadania/${task.id}`} style={{ textDecoration: "none" }}>
        <Box
          sx={{
            fontWeight: 600,
            color: "primary.main",
            "&:hover": { textDecoration: "underline" },
            "& .math-content": { display: "inline" },
          }}
        >
          <MathContent content={task.title} />
        </Box>
      </Link>
      {task.source_label && (
        <Typography variant="body2" sx={{ color: "grey.600" }}>
          {task.source_label}
        </Typography>
      )}
      <Box sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap", mt: "auto" }}>
        {task.category && <CategoryBadge category={task.category} size="small" />}
        {task.difficulty && <DifficultyStars difficulty={task.difficulty} size="small" />}
        {colors ? (
          <Chip
            label={`Najlepiej: ${task.best_score}/6`}
            size="small"
            sx={{ bgcolor: colors.bg, color: colors.color, border: `1px solid ${colors.border}`, fontWeight: 600 }}
          />
        ) : (
          <Chip
            label={task.attempts ? `Próby: ${task.attempts}` : "Jeszcze nie rozwiązane"}
            size="small"
            sx={{ bgcolor: "grey.100" }}
          />
        )}
      </Box>
      <Typography variant="caption" sx={{ color: "grey.600" }}>
        Ostatnio: {formatDate(task.last_activity_at)}
      </Typography>
    </Paper>
  );
}
