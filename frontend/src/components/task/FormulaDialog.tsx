"use client";

import dynamic from "next/dynamic";
import { useState } from "react";
import {
  Button,
  Checkbox,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import { EditorLoadBoundary } from "./EditorLoadBoundary";
import { sanitizeLatex } from "@/lib/utils/solutionText";

// MathLive is loaded the first time the dialog opens, never on the server
const MathFieldInput = dynamic(() => import("./MathFieldInput").then((m) => m.MathFieldInput), {
  ssr: false,
  loading: () => <CircularProgress size={24} aria-label="Ładowanie edytora wzorów" />,
});

export interface FormulaDialogProps {
  open: boolean;
  /** Source of the formula being corrected; "" when inserting a new one */
  initialLatex: string;
  initialDisplay: boolean;
  mode: "insert" | "edit";
  onClose: () => void;
  /** Receives sanitized LaTeX (placeholders stripped, whitespace collapsed) */
  onSubmit: (latex: string, display: boolean) => void;
}

/**
 * Visual formula editor. Full-screen on phones so the field stays visible
 * above MathLive's virtual keyboard, which covers the bottom third of the screen.
 */
export function FormulaDialog({ open, initialLatex, initialDisplay, mode, onClose, onSubmit }: FormulaDialogProps) {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down("sm"));
  const [latex, setLatex] = useState(initialLatex);
  const [display, setDisplay] = useState(initialDisplay);
  const [wasOpen, setWasOpen] = useState(open);

  // Start from the caller's formula each time the dialog opens (state adjusted
  // during render rather than in an effect - no extra render with stale values)
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setLatex(initialLatex);
      setDisplay(initialDisplay);
    }
  }

  const clean = sanitizeLatex(latex);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen={fullScreen}
      fullWidth
      maxWidth="sm"
      aria-labelledby="formula-dialog-title"
    >
      <DialogTitle id="formula-dialog-title">{mode === "edit" ? "Popraw wzór" : "Wstaw wzór"}</DialogTitle>
      <DialogContent>
        <EditorLoadBoundary>
          {open && <MathFieldInput initialLatex={initialLatex} onChange={setLatex} />}
        </EditorLoadBoundary>
        <FormControlLabel
          sx={{ mt: 1.5 }}
          control={<Checkbox checked={display} onChange={(e) => setDisplay(e.target.checked)} />}
          label="Wzór w osobnej linii"
        />
        <Typography variant="caption" component="p" sx={{ color: "grey.600" }}>
          Pisz jak na kalkulatorze: / robi ułamek, ^ potęgę, „sqrt” pierwiastek. Na telefonie
          pojawi się klawiatura z symbolami.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Anuluj</Button>
        <Button variant="contained" disabled={!clean} onClick={() => onSubmit(clean, display)}>
          {mode === "edit" ? "Zapisz" : "Wstaw"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
