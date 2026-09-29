"use client";

import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent, type MouseEvent } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  TextField,
  Typography,
} from "@mui/material";
import FunctionsIcon from "@mui/icons-material/Functions";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import { MathContent } from "@/components/ui/MathContent";
import { FormulaDialog } from "./FormulaDialog";
import {
  SolutionFileError,
  countChars,
  findMathSpans,
  formatCount,
  insertFormula,
  normalizeSolutionText,
  readSolutionFile,
  replaceMathSpan,
  type MathSpan,
} from "@/lib/utils/solutionText";

export interface SolutionTextEditorProps {
  value: string;
  onChange: (value: string) => void;
  maxChars: number;
  disabled?: boolean;
}

const visuallyHidden = {
  position: "absolute",
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
  border: 0,
} as const;

type FormulaTarget = { kind: "insert"; start: number; end: number } | { kind: "edit"; span: MathSpan };

function mathIndexOf(target: EventTarget | null): number | null {
  const hit = (target as HTMLElement | null)?.closest?.("[data-math-index]");
  const raw = hit?.getAttribute("data-math-index");
  return raw == null ? null : Number(raw);
}

/**
 * Textarea for a typed solution with a KaTeX preview. Formulas go in through
 * the MathLive dialog ("Wstaw wzór") at the cursor; a formula in the preview
 * can be clicked to reopen it. A .txt/.tex file is read in the browser into
 * the field for review - it is never uploaded as a file.
 *
 * The field is deliberately not hard-limited with maxLength: a loaded file
 * that is too long is shown in full with a red counter so the student can
 * trim it; the parent keeps the submit button disabled meanwhile.
 */
export function SolutionTextEditor({ value, onChange, maxChars, disabled = false }: SolutionTextEditorProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [target, setTarget] = useState<FormulaTarget | null>(null);
  // A fresh object per request, so the same position twice still moves the caret
  const [caret, setCaret] = useState<{ at: number } | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [pendingFileText, setPendingFileText] = useState<string | null>(null);

  const count = countChars(normalizeSolutionText(value));
  const over = count > maxChars;

  // Put the caret after what was just inserted, once React has rendered it
  useEffect(() => {
    const el = inputRef.current;
    if (!caret || !el) return;
    el.focus();
    el.setSelectionRange(caret.at, caret.at);
  }, [caret]);

  const openInsert = () => {
    const el = inputRef.current;
    const start = el?.selectionStart ?? value.length;
    const end = el?.selectionEnd ?? start;
    setTarget({ kind: "insert", start, end });
  };

  const openEdit = (index: number) => {
    const span = findMathSpans(value)[index];
    if (span) setTarget({ kind: "edit", span });
  };

  const applyFormula = (latex: string, display: boolean) => {
    if (!target) return;
    if (target.kind === "insert") {
      const result = insertFormula(value, target.start, target.end, latex, display);
      onChange(result.text);
      setCaret({ at: result.cursor });
    } else {
      onChange(replaceMathSpan(value, target.span, latex, display));
      setCaret({ at: target.span.start });
    }
    setTarget(null);
  };

  const handlePreviewClick = (e: MouseEvent<HTMLDivElement>) => {
    const index = mathIndexOf(e.target);
    if (index !== null) openEdit(index);
  };

  const handlePreviewKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "Enter" && e.key !== " ") return;
    const index = mathIndexOf(e.target);
    if (index === null) return;
    e.preventDefault();
    openEdit(index);
  };

  const handleFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setFileError(null);
    try {
      const text = await readSolutionFile(file);
      if (value.trim()) setPendingFileText(text);
      else onChange(text);
    } catch (err) {
      setFileError(err instanceof SolutionFileError ? err.message : "Nie udało się wczytać pliku.");
    }
  };

  return (
    <Box>
      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: 1 }}>
        <Button variant="outlined" startIcon={<FunctionsIcon />} onClick={openInsert} disabled={disabled}>
          Wstaw wzór
        </Button>
        <Button
          component="label"
          role={undefined}
          tabIndex={-1}
          variant="outlined"
          startIcon={<UploadFileIcon />}
          disabled={disabled}
          sx={{
            "&:has(input:focus-visible)": {
              outline: "3px solid",
              outlineColor: "primary.main",
              outlineOffset: "2px",
            },
          }}
        >
          Wczytaj plik .txt / .tex
          <input
            type="file"
            accept=".txt,.tex,text/plain"
            onChange={handleFile}
            disabled={disabled}
            style={visuallyHidden}
          />
        </Button>
      </Box>

      {fileError && (
        <Alert severity="warning" sx={{ mb: 1 }} onClose={() => setFileError(null)}>
          {fileError}
        </Alert>
      )}

      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
        <Box>
          <TextField
            id="solution-text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            disabled={disabled}
            multiline
            minRows={6}
            fullWidth
            placeholder="Wpisz swoje rozwiązanie. Wzory wstawisz przyciskiem „Wstaw wzór”."
            inputRef={inputRef}
            slotProps={{ htmlInput: { "aria-label": "Tekst rozwiązania", spellCheck: false } }}
            error={over}
          />
          <Typography
            variant="caption"
            component="p"
            sx={{ textAlign: "right", mt: 0.5, color: over ? "error.main" : "grey.600", fontWeight: over ? 600 : 400 }}
          >
            {formatCount(count)} / {formatCount(maxChars)}
            {over && " – skróć tekst, żeby wysłać rozwiązanie"}
          </Typography>
        </Box>

        <Box>
          <Box
            role="region"
            aria-label="Podgląd rozwiązania"
            sx={{
              p: 1.5,
              minHeight: 170,
              bgcolor: "grey.50",
              border: 1,
              borderColor: "grey.200",
              borderRadius: 1,
              overflowWrap: "anywhere",
              "& .math-src": { cursor: "pointer", borderRadius: 0.5, px: 0.25, outline: "1px dashed transparent" },
              "& .math-src:hover, & .math-src:focus-visible": { outlineColor: "primary.main", bgcolor: "primary.50" },
              "& .math-src--display": { display: "block" },
            }}
          >
            <Typography variant="caption" component="p" sx={{ color: "grey.600", mb: 0.5 }}>
              Podgląd
            </Typography>
            {/* role="presentation": the div only catches clicks bubbling from the
                formula spans, which are the real buttons (role="button", tabindex=0) */}
            <Box role="presentation" onClick={handlePreviewClick} onKeyDown={handlePreviewKey}>
              {value.trim() ? (
                <MathContent content={value} indexMath />
              ) : (
                <Typography variant="body2" sx={{ color: "grey.500", fontStyle: "italic" }}>
                  Tutaj zobaczysz swoje rozwiązanie ze wzorami.
                </Typography>
              )}
            </Box>
          </Box>
          <Typography variant="caption" component="p" sx={{ color: "grey.600", mt: 0.5 }}>
            Kliknij wzór w podglądzie, żeby go poprawić.
          </Typography>
        </Box>
      </Box>

      <FormulaDialog
        open={target !== null}
        mode={target?.kind === "edit" ? "edit" : "insert"}
        initialLatex={target?.kind === "edit" ? target.span.source : ""}
        initialDisplay={target?.kind === "edit" ? target.span.display : false}
        onClose={() => setTarget(null)}
        onSubmit={applyFormula}
      />

      <Dialog open={pendingFileText !== null} onClose={() => setPendingFileText(null)}>
        <DialogTitle>Zastąpić wpisany tekst?</DialogTitle>
        <DialogContent>
          <DialogContentText>Wczytany plik zastąpi tekst, który jest teraz w polu.</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingFileText(null)}>Anuluj</Button>
          <Button
            variant="contained"
            onClick={() => {
              if (pendingFileText !== null) onChange(pendingFileText);
              setPendingFileText(null);
            }}
          >
            Zastąp
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
