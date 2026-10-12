"use client";

import { Box, Button } from "@mui/material";
import ArrowBack from "@mui/icons-material/ArrowBack";
import { ReactNode } from "react";

interface StepActionsProps {
  /** Glowny przycisk (zwykle SubmitButton) */
  children?: ReactNode;
  onBack?: () => void;
  backDisabled?: boolean;
}

/**
 * "Wstecz" po lewej, glowna akcja po prawej. Na telefonie glowna akcja jest
 * na gorze i na cala szerokosc, "Wstecz" pod nia.
 */
export function StepActions({ children, onBack, backDisabled }: StepActionsProps) {
  return (
    <Box
      sx={{
        mt: 3,
        display: "flex",
        flexDirection: { xs: "column-reverse", sm: "row" },
        justifyContent: onBack ? "space-between" : "flex-end",
        alignItems: { xs: "stretch", sm: "center" },
        gap: 1.5,
      }}
    >
      {onBack && (
        <Button
          type="button"
          onClick={onBack}
          disabled={backDisabled}
          startIcon={<ArrowBack />}
          sx={{ py: 1.25, color: "grey.700" }}
        >
          Wstecz
        </Button>
      )}
      {children}
    </Box>
  );
}
