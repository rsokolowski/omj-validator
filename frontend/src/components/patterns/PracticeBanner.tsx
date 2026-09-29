import Link from "next/link";
import { Box, Paper, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { Pattern } from "@/lib/types";

/** Shown on a task page opened from a pattern card ("Rozwiąż zadanie"). */
export function PracticeBanner({ pattern }: { pattern: Pattern }) {
  return (
    <Paper sx={{ p: 2, mb: 3, bgcolor: "#eff6ff", border: "1px solid #bfdbfe" }} elevation={0}
      data-testid="practice-banner">
      <Typography variant="subtitle2" sx={{ color: "#1e40af" }}>
        Ćwiczysz wzorzec
      </Typography>
      <Box sx={{ fontWeight: 600, "& .math-content": { display: "inline" } }}>
        <MathContent content={pattern.trigger} />
      </Box>
      <Typography variant="body2" sx={{ color: "grey.700", mt: 0.5 }}>
        Ocena Twojego rozwiązania zaliczy się jako powtórka tego wzorca (wskazówki obniżają ją
        do &bdquo;z trudem&rdquo;). <Link href={`/wzorce/${pattern.id}`}>Pokaż wzorzec</Link>
      </Typography>
    </Paper>
  );
}
