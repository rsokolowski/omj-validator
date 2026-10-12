"use client";

import { useState } from "react";
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

function RegulaminLink({ children }: { children: React.ReactNode }) {
  return (
    <MuiLink
      component={Link}
      href="/regulamin"
      target="_blank"
      rel="noopener noreferrer"
      sx={{ color: "primary.main" }}
    >
      {children}
    </MuiLink>
  );
}

/**
 * Akceptacja regulaminu i zgoda osoby 16+ (zapisywana jako zgoda typu "self").
 *
 * Dwa osobne pola, bo zgoda na przetwarzanie danych musi byc wyraznie
 * odrozniona od akceptacji regulaminu (art. 7 ust. 2 RODO). API przyjmuje
 * jedno pole accept_terms - onChange zwraca true dopiero, gdy zaznaczone sa oba.
 */
export function TermsCheckbox({ checked, onChange, error, disabled }: TermsCheckboxProps) {
  const [terms, setTerms] = useState(checked);
  const [consent, setConsent] = useState(checked);
  const describedBy = error ? "terms-error" : undefined;

  const update = (nextTerms: boolean, nextConsent: boolean) => {
    setTerms(nextTerms);
    setConsent(nextConsent);
    onChange(nextTerms && nextConsent);
  };

  const inputProps = {
    "aria-describedby": describedBy,
    "aria-invalid": error ? true : undefined,
  } as React.InputHTMLAttributes<HTMLInputElement>;

  return (
    <Box
      sx={{
        bgcolor: "grey.50",
        borderRadius: 2,
        p: 2,
        border: "1px solid",
        borderColor: error ? "error.main" : "grey.200",
        display: "flex",
        flexDirection: "column",
        gap: 1.5,
      }}
    >
      <FormControlLabel
        control={
          <Checkbox
            checked={terms}
            onChange={(e) => update(e.target.checked, consent)}
            disabled={disabled}
            sx={{ mt: -1, alignSelf: "flex-start" }}
            slotProps={{ input: inputProps }}
          />
        }
        label={
          <Typography variant="body2" sx={{ color: "grey.700" }}>
            Akceptuję <RegulaminLink>regulamin serwisu</RegulaminLink>.
          </Typography>
        }
        sx={{ alignItems: "flex-start", m: 0 }}
      />
      <FormControlLabel
        control={
          <Checkbox
            checked={consent}
            onChange={(e) => update(terms, e.target.checked)}
            disabled={disabled}
            sx={{ mt: -1, alignSelf: "flex-start" }}
            slotProps={{ input: inputProps }}
          />
        }
        label={
          <Typography variant="body2" sx={{ color: "grey.700" }}>
            Zgadzam się na przetwarzanie moich danych, w tym zdjęć i tekstu moich
            rozwiązań, żeby serwis mógł je ocenić i prowadzić moje konto &ndash;
            także na ich przesłanie do firmy Google w USA, a gdy jej usługa nie
            działa, do firmy Anthropic w USA. Szczegóły są w punktach 6&ndash;8{" "}
            <RegulaminLink>polityki prywatności</RegulaminLink>. Zgodę mogę w
            każdej chwili cofnąć, usuwając konto.
          </Typography>
        }
        sx={{ alignItems: "flex-start", m: 0 }}
      />
      {error && (
        <FormHelperText id="terms-error" error sx={{ ml: 0 }}>
          {error}
        </FormHelperText>
      )}
    </Box>
  );
}
