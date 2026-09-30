"use client";

import { Box, Button, Paper, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { PatternVariant } from "@/lib/types";

interface VariantCardProps {
  variant: PatternVariant;
  label: string;
  chosen?: boolean;
  actionLabel?: string;
  onChoose?: () => void;
  disabled?: boolean;
  /** Extra line under the pattern, e.g. why a suggestion is worth remembering */
  note?: string;
}

/** One proposed wording of a pattern, to pick with a button. */
export function VariantCard({ variant, label, chosen, actionLabel = "Wybierz", onChoose, disabled, note }: VariantCardProps) {
  return (
    <Paper
      variant="outlined"
      component="article"
      aria-label={label}
      sx={{
        p: 2,
        display: "flex",
        flexDirection: "column",
        gap: 1,
        borderColor: chosen ? "primary.main" : "grey.300",
        borderWidth: chosen ? 2 : 1,
      }}
    >
      <Typography variant="caption" sx={{ color: "grey.600", fontWeight: 600 }}>
        {label}
      </Typography>
      <Box>
        <Typography variant="body2" component="span" sx={{ color: "grey.600" }}>
          Kiedy widzę:{" "}
        </Typography>
        <MathContent content={variant.trigger} />
      </Box>
      <Box>
        <Typography variant="body2" component="span" sx={{ color: "grey.600" }}>
          Spróbuj:{" "}
        </Typography>
        <MathContent content={variant.action} />
      </Box>
      {variant.example && (
        <Box sx={{ color: "grey.700", fontSize: "0.9rem" }}>
          <MathContent content={`Przykład: ${variant.example}`} />
        </Box>
      )}
      {note && (
        <Typography variant="body2" component="div" sx={{ color: "#1e40af" }}>
          <MathContent content={note} />
        </Typography>
      )}
      {onChoose && (
        <Box sx={{ mt: "auto" }}>
          <Button size="small" variant={chosen ? "contained" : "outlined"} onClick={onChoose} disabled={disabled}>
            {chosen ? "Wybrano" : actionLabel}
          </Button>
        </Box>
      )}
    </Paper>
  );
}
