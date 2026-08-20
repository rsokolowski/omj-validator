import { Tooltip, Box } from "@mui/material";
import { DIFFICULTY_LABELS } from "@/lib/utils/constants";

interface DifficultyStarsProps {
  difficulty: number;
  size?: "small" | "medium";
}

/**
 * Poziom trudności jako gwiazdki.
 *
 * Dostępność (WCAG 1.1.1, 1.4.1, 4.1.2): informacja nie może być niesiona samym
 * kolorem ani ciągiem znaków "★★★☆☆", którego czytnik ekranu odczyta dosłownie
 * albo pominie. Element ma więc rolę `img` i pełną nazwę tekstową, a same
 * gwiazdki są przed czytnikiem ukryte. Rola jest tu konieczna również dlatego,
 * że `aria-label` na elemencie o roli `generic` (zwykły `<span>`) jest przez
 * czytniki ignorowany.
 */
export function DifficultyStars({ difficulty, size = "medium" }: DifficultyStarsProps) {
  const filledStars = "★".repeat(difficulty);
  const emptyStars = "☆".repeat(5 - difficulty);
  const description = DIFFICULTY_LABELS[difficulty] || "";
  const label = description
    ? `Poziom trudności ${difficulty} z 5: ${description}`
    : `Poziom trudności ${difficulty} z 5`;

  const fontSize = size === "small" ? "0.75rem" : "0.875rem";

  return (
    <Tooltip title={description} arrow>
      <Box
        component="span"
        role="img"
        aria-label={label}
        className={`difficulty-${difficulty}`}
        sx={{
          fontSize,
          letterSpacing: size === "small" ? "-1px" : "1px",
          cursor: "help",
        }}
      >
        <span aria-hidden="true">
          {filledStars}
          {emptyStars}
        </span>
      </Box>
    </Tooltip>
  );
}
