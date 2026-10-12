"use client";

import { TextField } from "@mui/material";

interface ParentEmailFieldProps {
  value: string;
  onChange: (value: string) => void;
  error?: string | null;
  disabled?: boolean;
  id?: string;
  autoFocus?: boolean;
  label?: string;
}

export function ParentEmailField({
  value,
  onChange,
  error,
  disabled,
  id = "parent-email",
  autoFocus,
  label = "E-mail rodzica lub opiekuna",
}: ParentEmailFieldProps) {
  return (
    <TextField
      id={id}
      label={label}
      type="email"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      error={Boolean(error)}
      helperText={error || "Na przykład mama@example.com"}
      fullWidth
      autoFocus={autoFocus}
      // "off": przegladarka podpowiadalaby adres samego dziecka
      autoComplete="off"
      slotProps={{
        htmlInput: { inputMode: "email", autoCapitalize: "none", autoCorrect: "off", spellCheck: false },
      }}
    />
  );
}
