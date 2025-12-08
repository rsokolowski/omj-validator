"use client";

import { useState } from "react";
import { Paper, Typography, Box, Button, Collapse, IconButton } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";

interface HintsSectionProps {
  hints: string[];
}

export function HintsSection({ hints }: HintsSectionProps) {
  const [revealedCount, setRevealedCount] = useState(0);

  const revealNext = () => {
    if (revealedCount < hints.length) {
      setRevealedCount(revealedCount + 1);
    }
  };

  const hideAll = () => {
    setRevealedCount(0);
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}>
        <Typography variant="h6" sx={{ color: "grey.700" }}>
          Wskazówki ({revealedCount}/{hints.length})
        </Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          {revealedCount > 0 && (
            <Button size="small" variant="outlined" onClick={hideAll}>
              Ukryj wszystkie
            </Button>
          )}
          {revealedCount < hints.length && (
            <Button size="small" variant="contained" onClick={revealNext}>
              Pokaż wskazówkę {revealedCount + 1}
            </Button>
          )}
        </Box>
      </Box>

      <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {hints.map((hint, index) => (
          <Collapse key={index} in={index < revealedCount}>
            <Box
              sx={{
                p: 2,
                bgcolor: "amber.50",
                borderRadius: 1,
                borderLeft: 4,
                borderColor: "warning.main",
                backgroundColor: "#fffbeb",
              }}
            >
              <Typography variant="caption" sx={{ color: "grey.500", display: "block", mb: 0.5 }}>
                Wskazówka {index + 1}
              </Typography>
              <MathContent content={hint} />
            </Box>
          </Collapse>
        ))}
      </Box>

    </Paper>
  );
}
