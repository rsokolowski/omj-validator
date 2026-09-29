"use client";

import { Box, MenuItem, TextField, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { PatternDraft } from "@/lib/types";
import {
  CATEGORY_NAMES,
  PATTERN_ACTION_MAX,
  PATTERN_ACTION_MIN,
  PATTERN_EXAMPLE_MAX,
  PATTERN_RAW_MAX,
  PATTERN_TRIGGER_MAX,
  PATTERN_TRIGGER_MIN,
} from "@/lib/utils/constants";

/** Polish message for the first problem with a pattern to save, or null. */
export function validatePattern(draft: PatternDraft): string | null {
  const trigger = draft.trigger.trim();
  const action = draft.action.trim();
  if (trigger.length < PATTERN_TRIGGER_MIN) return "Uzupełnij, kiedy wzorzec się przydaje (\"Kiedy w treści widzę...\").";
  if (action.length < PATTERN_ACTION_MIN) return "Uzupełnij, co warto wtedy zrobić (\"...to warto spróbować...\").";
  if (trigger.length > PATTERN_TRIGGER_MAX) return `Wyzwalacz może mieć najwyżej ${PATTERN_TRIGGER_MAX} znaków.`;
  if (action.length > PATTERN_ACTION_MAX) return `Akcja może mieć najwyżej ${PATTERN_ACTION_MAX} znaków.`;
  if (draft.example.length > PATTERN_EXAMPLE_MAX) return `Przykład może mieć najwyżej ${PATTERN_EXAMPLE_MAX} znaków.`;
  return null;
}

/** Can the AI work with this draft: one free sentence, or trigger + action. */
export function canRefine(draft: PatternDraft): boolean {
  return Boolean(draft.raw.trim() || (draft.trigger.trim() && draft.action.trim()));
}

interface PatternEditorProps {
  value: PatternDraft;
  onChange: (value: PatternDraft) => void;
  category?: string;
  onCategoryChange?: (category: string) => void;
  disabled?: boolean;
  /** Show the free-text "idea in your own words" field */
  showRaw?: boolean;
}

export function PatternEditor({
  value,
  onChange,
  category,
  onCategoryChange,
  disabled,
  showRaw = false,
}: PatternEditorProps) {
  const set = (field: keyof PatternDraft) => (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange({ ...value, [field]: e.target.value });

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {showRaw && (
        <TextField
          id="pattern-raw"
          label="Twój pomysł własnymi słowami (opcjonalnie)"
          helperText="Możesz zacząć od jednego zdania - AI pomoże podzielić je na wyzwalacz i akcję."
          value={value.raw}
          onChange={set("raw")}
          disabled={disabled}
          multiline
          minRows={2}
          slotProps={{ htmlInput: { maxLength: PATTERN_RAW_MAX } }}
        />
      )}
      <TextField
        id="pattern-trigger"
        label="Kiedy w treści widzę…"
        placeholder="np. pytają, czy da się dojść do pewnego stanu"
        value={value.trigger}
        onChange={set("trigger")}
        disabled={disabled}
        multiline
        slotProps={{ htmlInput: { maxLength: PATTERN_TRIGGER_MAX } }}
      />
      <TextField
        id="pattern-action"
        label="…to warto spróbować…"
        placeholder="np. szukać niezmiennika - sprawdzić parzystość sumy"
        value={value.action}
        onChange={set("action")}
        disabled={disabled}
        multiline
        minRows={2}
        slotProps={{ htmlInput: { maxLength: PATTERN_ACTION_MAX } }}
      />
      <TextField
        id="pattern-example"
        label="Przykład (opcjonalnie)"
        helperText="Wzory w $LaTeX$, np. $n(n+1)$"
        value={value.example}
        onChange={set("example")}
        disabled={disabled}
        multiline
        slotProps={{ htmlInput: { maxLength: PATTERN_EXAMPLE_MAX } }}
      />
      {value.example.includes("$") && (
        <Box sx={{ bgcolor: "grey.50", p: 1.5, borderRadius: 1 }}>
          <Typography variant="caption" sx={{ color: "grey.600" }}>
            Podgląd przykładu
          </Typography>
          <MathContent content={value.example} />
        </Box>
      )}
      {onCategoryChange && (
        <TextField
          id="pattern-category"
          select
          label="Kategoria"
          value={category ?? ""}
          onChange={(e) => onCategoryChange(e.target.value)}
          disabled={disabled}
          sx={{ maxWidth: 280 }}
        >
          <MenuItem value="">(bez kategorii)</MenuItem>
          {Object.entries(CATEGORY_NAMES).map(([id, name]) => (
            <MenuItem key={id} value={id}>
              {name}
            </MenuItem>
          ))}
        </TextField>
      )}
    </Box>
  );
}
