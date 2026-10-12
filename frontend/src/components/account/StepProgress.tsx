"use client";

import { Box, LinearProgress, Typography } from "@mui/material";

interface StepProgressProps {
  step: number;
  total: number;
}

/** "Krok 2 z 4" + cienki pasek (pasek tylko wizualnie - tekst mowi to samo). */
export function StepProgress({ step, total }: StepProgressProps) {
  return (
    <Box sx={{ mb: 2.5 }}>
      <Typography variant="body2" sx={{ color: "grey.600", fontWeight: 500, mb: 0.75 }}>
        Krok {step} z {total}
      </Typography>
      <LinearProgress
        variant="determinate"
        value={(step / total) * 100}
        aria-hidden="true"
        sx={{ height: 6, borderRadius: 3, bgcolor: "grey.100" }}
      />
    </Box>
  );
}
