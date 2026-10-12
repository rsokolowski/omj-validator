"use client";

import { useState } from "react";
import { IconButton, InputAdornment, TextField } from "@mui/material";
import Visibility from "@mui/icons-material/Visibility";
import VisibilityOff from "@mui/icons-material/VisibilityOff";

interface PasswordFieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  /** "new-password" przy zakladaniu konta i zmianie hasla */
  autoComplete: "current-password" | "new-password";
  error?: string | null;
  helperText?: string;
  disabled?: boolean;
  onBlur?: () => void;
  autoFocus?: boolean;
}

/**
 * Pole hasla z przyciskiem "Pokaz haslo". Zamiast drugiego pola "Powtorz
 * haslo" - dziecko moze po prostu zobaczyc, co wpisalo.
 */
export function PasswordField({
  id,
  label,
  value,
  onChange,
  autoComplete,
  error,
  helperText,
  disabled,
  onBlur,
  autoFocus,
}: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);

  return (
    <TextField
      id={id}
      label={label}
      type={visible ? "text" : "password"}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onBlur={onBlur}
      autoComplete={autoComplete}
      autoFocus={autoFocus}
      disabled={disabled}
      error={Boolean(error)}
      helperText={error || helperText}
      fullWidth
      slotProps={{
        htmlInput: { autoCapitalize: "none", autoCorrect: "off", spellCheck: false },
        input: {
          endAdornment: (
            <InputAdornment position="end">
              {/* 48 px - wygodny cel dotyku (WCAG 2.5.8) */}
              <IconButton
                onClick={() => setVisible((v) => !v)}
                aria-label={visible ? "Ukryj hasło" : "Pokaż hasło"}
                aria-pressed={visible}
                aria-controls={id}
                edge="end"
                sx={{ width: 48, height: 48 }}
                disabled={disabled}
              >
                {visible ? <VisibilityOff /> : <Visibility />}
              </IconButton>
            </InputAdornment>
          ),
        },
      }}
    />
  );
}
