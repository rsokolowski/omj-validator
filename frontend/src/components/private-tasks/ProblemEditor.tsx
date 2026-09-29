"use client";

import { Box, MenuItem, TextField, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { PrivateTaskInput } from "@/lib/types";
import {
  CATEGORY_NAMES,
  DIFFICULTY_LABELS,
  PRIVATE_CONTENT_MAX,
  PRIVATE_CONTENT_MIN,
  PRIVATE_SOURCE_LABEL_MAX,
  PRIVATE_TITLE_MAX,
} from "@/lib/utils/constants";

export interface EditableTask {
  title: string;
  content: string;
  source_label: string;
  category: string;
  difficulty: string; // "" = let the AI decide
}

export function emptyTask(): EditableTask {
  return { title: "", content: "", source_label: "", category: "", difficulty: "" };
}

export function toInput(task: EditableTask): PrivateTaskInput {
  return {
    title: task.title.trim(),
    content: task.content.trim(),
    source_label: task.source_label.trim() || null,
    category: task.category || null,
    difficulty: task.difficulty ? Number(task.difficulty) : null,
  };
}

/** Polish message for the first problem with this task, or null when valid. */
export function validateTask(task: EditableTask): string | null {
  const title = task.title.trim();
  const content = task.content.trim();
  if (!title) return "Wpisz tytuł zadania.";
  if (title.length > PRIVATE_TITLE_MAX) return `Tytuł może mieć najwyżej ${PRIVATE_TITLE_MAX} znaków.`;
  if (content.length < PRIVATE_CONTENT_MIN)
    return `Treść zadania musi mieć co najmniej ${PRIVATE_CONTENT_MIN} znaków.`;
  if (content.length > PRIVATE_CONTENT_MAX)
    return `Treść zadania może mieć najwyżej ${PRIVATE_CONTENT_MAX} znaków.`;
  if (task.source_label.trim().length > PRIVATE_SOURCE_LABEL_MAX)
    return `Źródło może mieć najwyżej ${PRIVATE_SOURCE_LABEL_MAX} znaków.`;
  return null;
}

interface ProblemEditorProps {
  value: EditableTask;
  onChange: (value: EditableTask) => void;
  /** Unique prefix for field ids (several editors can share a page) */
  idPrefix: string;
  disabled?: boolean;
  /** Offer "let the AI decide" for category and difficulty (new tasks only) */
  allowAuto?: boolean;
}

/**
 * Edit a task statement with a live preview of how it will be rendered.
 * Math goes between dollar signs, the same notation the AI uses when it reads
 * a photo - so a misread formula can be fixed right here.
 */
export function ProblemEditor({ value, onChange, idPrefix, disabled, allowAuto = true }: ProblemEditorProps) {
  const set = (field: keyof EditableTask) => (e: React.ChangeEvent<HTMLInputElement>) =>
    onChange({ ...value, [field]: e.target.value });

  return (
    <Box sx={{ display: "grid", gap: 2 }}>
      <TextField
        id={`${idPrefix}-title`}
        label="Tytuł"
        value={value.title}
        onChange={set("title")}
        disabled={disabled}
        required
        fullWidth
        size="small"
        slotProps={{ htmlInput: { maxLength: PRIVATE_TITLE_MAX } }}
      />
      <TextField
        id={`${idPrefix}-content`}
        label="Treść zadania"
        value={value.content}
        onChange={set("content")}
        disabled={disabled}
        required
        fullWidth
        multiline
        minRows={4}
        helperText="Wzory zapisuj między znakami dolara, np. $x^2 + 1$ albo $\frac{1}{2}$."
        slotProps={{ htmlInput: { maxLength: PRIVATE_CONTENT_MAX, spellCheck: false } }}
      />
      {value.content.trim() && (
        <Box
          sx={{ p: 2, bgcolor: "grey.50", borderRadius: 1, border: 1, borderColor: "grey.200" }}
          aria-label="Podgląd treści zadania"
          role="region"
        >
          <Typography variant="caption" component="p" sx={{ color: "grey.600", mb: 0.5 }}>
            Podgląd
          </Typography>
          <MathContent content={value.content} className="text-gray-800" />
        </Box>
      )}
      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "2fr 1fr 1fr" } }}>
        <TextField
          id={`${idPrefix}-source`}
          label="Źródło (opcjonalnie)"
          placeholder="np. IKOMJ 4.3, Kangur 2024/27"
          value={value.source_label}
          onChange={set("source_label")}
          disabled={disabled}
          size="small"
          slotProps={{ htmlInput: { maxLength: PRIVATE_SOURCE_LABEL_MAX } }}
        />
        <TextField
          id={`${idPrefix}-category`}
          select
          label="Kategoria"
          value={value.category}
          onChange={set("category")}
          disabled={disabled}
          size="small"
        >
          {allowAuto && <MenuItem value="">Dobierze AI</MenuItem>}
          {Object.entries(CATEGORY_NAMES).map(([key, name]) => (
            <MenuItem key={key} value={key}>
              {name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          id={`${idPrefix}-difficulty`}
          select
          label="Trudność"
          value={value.difficulty}
          onChange={set("difficulty")}
          disabled={disabled}
          size="small"
        >
          {allowAuto && <MenuItem value="">Dobierze AI</MenuItem>}
          {[1, 2, 3, 4, 5].map((level) => (
            <MenuItem key={level} value={String(level)} title={DIFFICULTY_LABELS[level]}>
              {level} – {DIFFICULTY_LABELS[level]?.split(" - ")[0]}
            </MenuItem>
          ))}
        </TextField>
      </Box>
    </Box>
  );
}
