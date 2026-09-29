import Link from "next/link";
import { Box, Chip, Paper } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { Pattern } from "@/lib/types";
import { PATTERN_LEVEL_NAMES } from "@/lib/utils/constants";
import { formatDay } from "./formatDay";

export function PatternCard({ pattern }: { pattern: Pattern }) {
  return (
    <Paper component="article" sx={{ p: 2.5, display: "flex", flexDirection: "column", gap: 1, height: "100%" }}>
      <Link href={`/wzorce/${pattern.id}`} style={{ textDecoration: "none" }}>
        <Box sx={{ fontWeight: 600, color: "primary.main", "&:hover": { textDecoration: "underline" } }}>
          <MathContent content={pattern.trigger} />
        </Box>
      </Link>
      <Box sx={{ color: "grey.700", fontSize: "0.9rem" }}>
        <MathContent content={`→ ${pattern.action}`} />
      </Box>
      <Box sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap", mt: "auto" }}>
        {pattern.category && <CategoryBadge category={pattern.category} size="small" />}
        <Chip size="small" label={PATTERN_LEVEL_NAMES[pattern.level] ?? `Poziom ${pattern.level}`} sx={{ bgcolor: "grey.100" }} />
        {pattern.is_due ? (
          <Chip size="small" color="warning" label="Do powtórki dziś" />
        ) : (
          <Chip size="small" variant="outlined" label={`Powtórka: ${formatDay(pattern.due_on)}`} />
        )}
        {pattern.suggested_links_count > 0 && (
          <Chip size="small" color="info" variant="outlined" label={`Propozycje zadań: ${pattern.suggested_links_count}`} />
        )}
      </Box>
    </Paper>
  );
}
