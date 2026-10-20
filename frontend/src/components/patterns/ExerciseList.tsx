import Link from "next/link";
import { Box, Chip, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { ExerciseSummary } from "@/lib/types";
import { EXERCISE_LEVEL_LABELS } from "@/lib/utils/constants";

export function ExerciseLevelChip({ level }: { level: string | null }) {
  if (!level) return null;
  const easy = level === "easy";
  return (
    <Chip
      size="small"
      label={EXERCISE_LEVEL_LABELS[level] ?? level}
      sx={{
        bgcolor: easy ? "#dcfce7" : "#fef3c7",
        color: easy ? "#166534" : "#92400e",
        fontWeight: 600,
        height: 22,
      }}
    />
  );
}

/** Solved = 5 or 6 points, as for a practice task */
export function solvedCount(exercises: ExerciseSummary[]): number {
  return exercises.filter((e) => e.best_score !== null && e.best_score >= 5).length;
}

/** Numbered rows: title, level, best score; each opens the exercise in Moje zadania. */
export function ExerciseList({ exercises }: { exercises: ExerciseSummary[] }) {
  return (
    <Box component="ol" sx={{ m: 0, p: 0, listStyle: "none" }} data-testid="exercise-list">
      {exercises.map((exercise, index) => (
        <Box
          component="li"
          key={exercise.id}
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 2,
            py: 1,
            borderBottom: 1,
            borderColor: "grey.200",
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap", minWidth: 0 }}>
            <Typography component="span" sx={{ color: "grey.600", minWidth: "1.5em" }}>
              {index + 1}.
            </Typography>
            <Link href={`/moje-zadania/${exercise.id}`} style={{ textDecoration: "none" }}>
              <Box
                sx={{
                  color: "primary.main",
                  fontWeight: 500,
                  "&:hover": { textDecoration: "underline" },
                  "& .math-content": { display: "inline" },
                }}
              >
                <MathContent content={exercise.title} />
              </Box>
            </Link>
            <ExerciseLevelChip level={exercise.exercise_level} />
          </Box>
          <Typography variant="body2" sx={{ color: "grey.700", whiteSpace: "nowrap" }}>
            {exercise.best_score !== null ? `${exercise.best_score}/6` : exercise.attempts ? "próba" : "—"}
          </Typography>
        </Box>
      ))}
    </Box>
  );
}
