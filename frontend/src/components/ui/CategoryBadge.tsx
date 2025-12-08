import { Chip, Tooltip } from "@mui/material";
import { CATEGORY_NAMES, CATEGORY_TOOLTIPS } from "@/lib/utils/constants";

interface CategoryBadgeProps {
  category: string;
  size?: "small" | "medium";
}

const CATEGORY_COLORS: Record<string, { bg: string; color: string }> = {
  algebra: { bg: "#dbeafe", color: "#1e40af" },
  geometria: { bg: "#dcfce7", color: "#166534" },
  teoria_liczb: { bg: "#fef3c7", color: "#92400e" },
  kombinatoryka: { bg: "#f3e8ff", color: "#7c3aed" },
  logika: { bg: "#ffe4e6", color: "#be123c" },
  arytmetyka: { bg: "#e0f2fe", color: "#0369a1" },
};

export function CategoryBadge({ category, size = "medium" }: CategoryBadgeProps) {
  const name = CATEGORY_NAMES[category] || category;
  const tooltip = CATEGORY_TOOLTIPS[category] || "";
  const colors = CATEGORY_COLORS[category] || { bg: "#f3f4f6", color: "#374151" };

  return (
    <Tooltip title={tooltip} arrow>
      <Chip
        label={name}
        size={size}
        sx={{
          bgcolor: colors.bg,
          color: colors.color,
          fontWeight: 500,
          fontSize: size === "small" ? "0.65rem" : "0.8125rem",
          height: size === "small" ? 20 : 28,
          cursor: "help",
          "&:hover": {
            transform: "translateY(-1px)",
          },
        }}
      />
    </Tooltip>
  );
}
