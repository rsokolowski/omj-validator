import { Tooltip, Box } from "@mui/material";
import { DIFFICULTY_LABELS } from "@/lib/utils/constants";

interface DifficultyStarsProps {
  difficulty: number;
  size?: "small" | "medium";
}

export function DifficultyStars({ difficulty, size = "medium" }: DifficultyStarsProps) {
  const filledStars = "★".repeat(difficulty);
  const emptyStars = "☆".repeat(5 - difficulty);
  const tooltip = DIFFICULTY_LABELS[difficulty] || "";

  const fontSize = size === "small" ? "0.75rem" : "0.875rem";

  return (
    <Tooltip title={tooltip} arrow>
      <Box
        component="span"
        className={`difficulty-${difficulty}`}
        sx={{
          fontSize,
          letterSpacing: size === "small" ? "-1px" : "1px",
          cursor: "help",
        }}
      >
        {filledStars}
        {emptyStars}
      </Box>
    </Tooltip>
  );
}
