"use client";

import { ReactNode } from "react";
import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
} from "@mui/material";

interface ConfirmDialogProps {
  open: boolean;
  id: string;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  busyLabel: string;
  busy: boolean;
  error?: string | null;
  onConfirm: () => void;
  onClose: () => void;
  color?: "primary" | "error";
}

/** Okno potwierdzenia nieodwracalnej akcji; na telefonie przyciski jeden pod drugim. */
export function ConfirmDialog({
  open,
  id,
  title,
  children,
  confirmLabel,
  busyLabel,
  busy,
  error,
  onConfirm,
  onClose,
  color = "error",
}: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={busy ? undefined : onClose}
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-description`}
      maxWidth="sm"
      fullWidth
      sx={{ "& .MuiDialog-paper": { mx: 2, width: "calc(100% - 32px)" } }}
    >
      <DialogTitle id={`${id}-title`} sx={{ fontWeight: 700 }}>
        {title}
      </DialogTitle>
      <DialogContent id={`${id}-description`}>
        {children}
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
      </DialogContent>
      <DialogActions
        sx={{
          px: 3,
          pb: 2.5,
          gap: 1,
          flexDirection: { xs: "column-reverse", sm: "row" },
          alignItems: "stretch",
          "& > :not(style) ~ :not(style)": { ml: { xs: 0, sm: 1 } },
        }}
      >
        <Button onClick={onClose} disabled={busy} sx={{ py: 1.25 }}>
          Anuluj
        </Button>
        <Button
          variant="contained"
          color={color}
          onClick={onConfirm}
          disabled={busy}
          aria-busy={busy || undefined}
          startIcon={busy ? <CircularProgress size={16} color="inherit" /> : undefined}
          sx={{ py: 1.25 }}
        >
          {busy ? busyLabel : confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
