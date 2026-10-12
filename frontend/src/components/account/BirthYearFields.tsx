"use client";

import {
  Box,
  FormControl,
  FormControlLabel,
  FormHelperText,
  FormLabel,
  Radio,
  RadioGroup,
  TextField,
} from "@mui/material";
import { birthYearOptions, isAmbiguousBirthYear } from "@/lib/utils/account";

interface BirthYearFieldsProps {
  currentYear: number;
  birthYear: number | null;
  turned16: boolean | null;
  onBirthYearChange: (year: number | null) => void;
  onTurned16Change: (value: boolean) => void;
  birthYearError?: string | null;
  turned16Error?: string | null;
  disabled?: boolean;
}

/**
 * Rok urodzenia (natywna lista - na telefonie otwiera wygodne kolko wyboru)
 * i pytanie uzupelniajace, gdy ktos konczy 16 lat w tym roku.
 */
export function BirthYearFields({
  currentYear,
  birthYear,
  turned16,
  onBirthYearChange,
  onTurned16Change,
  birthYearError,
  turned16Error,
  disabled,
}: BirthYearFieldsProps) {
  const years = birthYearOptions(currentYear);
  const ambiguous = birthYear !== null && isAmbiguousBirthYear(birthYear, currentYear);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <TextField
        id="birth-year"
        select
        label="Rok urodzenia"
        value={birthYear === null ? "" : String(birthYear)}
        onChange={(e) => onBirthYearChange(e.target.value ? Number(e.target.value) : null)}
        error={Boolean(birthYearError)}
        helperText={birthYearError || " "}
        disabled={disabled}
        fullWidth
        slotProps={{ select: { native: true }, inputLabel: { shrink: true } }}
      >
        <option value="">Wybierz rok</option>
        {years.map((year) => (
          <option key={year} value={year}>
            {year}
          </option>
        ))}
      </TextField>

      {ambiguous && (
        <FormControl error={Boolean(turned16Error)} disabled={disabled}>
          <FormLabel id="turned-16-label" sx={{ color: "grey.900", fontWeight: 600, mb: 1 }}>
            Czy masz już ukończone 16 lat?
          </FormLabel>
          <RadioGroup
            aria-labelledby="turned-16-label"
            value={turned16 === null ? "" : turned16 ? "tak" : "nie"}
            onChange={(e) => onTurned16Change(e.target.value === "tak")}
            sx={{ gap: 1 }}
          >
            {[
              { value: "tak", label: "Tak, 16. urodziny mam już za sobą" },
              { value: "nie", label: "Nie, urodziny mam dopiero w tym roku" },
            ].map((option) => (
              <FormControlLabel
                key={option.value}
                value={option.value}
                control={<Radio />}
                label={option.label}
                sx={{
                  m: 0,
                  pr: 2,
                  py: 0.5,
                  border: "1px solid",
                  borderColor: "grey.300",
                  borderRadius: 2,
                }}
              />
            ))}
          </RadioGroup>
          {turned16Error && <FormHelperText sx={{ ml: 0 }}>{turned16Error}</FormHelperText>}
        </FormControl>
      )}
    </Box>
  );
}
