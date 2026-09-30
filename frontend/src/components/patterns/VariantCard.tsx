"use client";

import { Box, Button, Paper, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { RoundVariant } from "@/lib/types";
import { taskRef } from "@/lib/utils/patternTasks";
import { TaskChip, TextWithTasks } from "./TaskChip";

interface VariantCardProps {
  variant: RoundVariant;
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
      {variant.note && (
        <Typography variant="body2" component="div" sx={{ color: "grey.700", fontStyle: "italic" }}>
          <TextWithTasks text={variant.note} />
        </Typography>
      )}
      {variant.tasks && <VariantTasks keys={variant.tasks} />}
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

/** OMJ tasks where the version helps - how broad it is, shown rather than argued. */
function VariantTasks({ keys }: { keys: string[] }) {
  const refs = keys.map(taskRef).filter((r) => r !== null);
  if (!refs.length) {
    return (
      <Typography variant="caption" sx={{ color: "grey.600" }}>
        Nie pasuje do żadnego zadania OMJ z listy AI.
      </Typography>
    );
  }
  return (
    <Box>
      <Typography variant="caption" sx={{ color: "grey.600", display: "block", mb: 0.5 }}>
        Pomaga w zadaniach OMJ ({refs.length}):
      </Typography>
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
        {refs.map((ref) => (
          <TaskChip key={ref.key} task={ref} />
        ))}
      </Box>
    </Box>
  );
}
