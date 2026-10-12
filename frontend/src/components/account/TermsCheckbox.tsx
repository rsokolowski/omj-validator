"use client";

import Link from "next/link";
import {
  Box,
  Checkbox,
  FormControlLabel,
  FormHelperText,
  Link as MuiLink,
  Typography,
} from "@mui/material";

interface TermsCheckboxProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  error?: string | null;
  disabled?: boolean;
}

/** Zgoda osoby 16+ (zapisywana jako zgoda typu "self"). */
export function TermsCheckbox({ checked, onChange, error, disabled }: TermsCheckboxProps) {
  return (
    <Box
      sx={{
        bgcolor: "grey.50",
        borderRadius: 2,
        p: 2,
        border: "1px solid",
        borderColor: error ? "error.main" : "grey.200",
      }}
    >
      <FormControlLabel
        control={
          <Checkbox
            checked={checked}
            onChange={(e) => onChange(e.target.checked)}
            disabled={disabled}
            sx={{ mt: -1, alignSelf: "flex-start" }}
            slotProps={{
              input: {
                "aria-describedby": error ? "terms-error" : undefined,
                "aria-invalid": error ? true : undefined,
              } as React.InputHTMLAttributes<HTMLInputElement>,
            }}
          />
        }
        label={
          <Typography variant="body2" sx={{ color: "grey.700" }}>
            Akceptuję{" "}
            <MuiLink
              component={Link}
              href="/regulamin"
              target="_blank"
              rel="noopener noreferrer"
              sx={{ color: "primary.main" }}
            >
              regulamin serwisu
            </MuiLink>{" "}
            i zgadzam się na przetwarzanie moich danych zgodnie z polityką prywatności.
          </Typography>
        }
        sx={{ alignItems: "flex-start", m: 0 }}
      />
      {error && (
        <FormHelperText id="terms-error" error sx={{ mt: 1, ml: 0 }}>
          {error}
        </FormHelperText>
      )}
    </Box>
  );
}
