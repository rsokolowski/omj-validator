"use client";

import { Button, CircularProgress } from "@mui/material";
import { ReactNode } from "react";

interface SubmitButtonProps {
  busy: boolean;
  busyLabel: string;
  children: ReactNode;
  disabled?: boolean;
  onClick?: () => void;
  type?: "submit" | "button";
  color?: "primary" | "error";
}

/**
 * Glowny przycisk formularza: na telefonie na cala szerokosc, w trakcie
 * zapytania zablokowany ze spinnerem (zapobiega podwojnemu wyslaniu).
 */
export function SubmitButton({
  busy,
  busyLabel,
  children,
  disabled,
  onClick,
  type = "submit",
  color = "primary",
}: SubmitButtonProps) {
  return (
    <Button
      type={type}
      variant="contained"
      size="large"
      color={color}
      onClick={onClick}
      disabled={busy || disabled}
      aria-busy={busy || undefined}
      startIcon={busy ? <CircularProgress size={18} color="inherit" /> : undefined}
      sx={{ py: 1.25, width: { xs: "100%", sm: "auto" }, minWidth: { sm: 180 } }}
    >
      {busy ? busyLabel : children}
    </Button>
  );
}
