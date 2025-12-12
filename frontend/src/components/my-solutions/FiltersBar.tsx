"use client";

import {
  Paper,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
  Typography,
  Button,
  FormControlLabel,
  Checkbox,
} from "@mui/material";
import FilterListIcon from "@mui/icons-material/FilterList";
import ClearIcon from "@mui/icons-material/Clear";
import { Filters } from "./MySolutionsDashboard";

interface FiltersBarProps {
  filters: Filters;
  onFilterChange: (filters: Filters) => void;
  totalCount: number;
}

// Generate year options (current year down to 2005)
const currentYear = new Date().getFullYear();
const YEARS = Array.from({ length: currentYear - 2004 }, (_, i) => (currentYear - i).toString());

export function FiltersBar({ filters, onFilterChange, totalCount }: FiltersBarProps) {
  const hasActiveFilters = filters.year || filters.etap || filters.showErrors;

  const handleYearChange = (year: string) => {
    onFilterChange({ ...filters, year });
  };

  const handleEtapChange = (etap: string) => {
    onFilterChange({ ...filters, etap });
  };

  const handleShowErrorsChange = (showErrors: boolean) => {
    onFilterChange({ ...filters, showErrors });
  };

  const handleClearFilters = () => {
    onFilterChange({ year: "", etap: "", showErrors: false });
  };

  return (
    <Paper
      sx={{
        p: 2,
        mb: 3,
        borderRadius: 2,
        border: "1px solid",
        borderColor: "grey.100",
      }}
    >
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={2}
        alignItems={{ xs: "stretch", sm: "center" }}
        flexWrap="wrap"
        useFlexGap
      >
        <Stack direction="row" spacing={1} alignItems="center">
          <FilterListIcon fontSize="small" color="action" />
          <Typography variant="body2" fontWeight={500} color="text.secondary">
            Filtry:
          </Typography>
        </Stack>

        <FormControl size="small" sx={{ minWidth: 100 }}>
          <InputLabel>Rok</InputLabel>
          <Select
            value={filters.year}
            label="Rok"
            onChange={(e) => handleYearChange(e.target.value)}
          >
            <MenuItem value="">Wszystkie</MenuItem>
            {YEARS.map((year) => (
              <MenuItem key={year} value={year}>
                {year}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Etap</InputLabel>
          <Select
            value={filters.etap}
            label="Etap"
            onChange={(e) => handleEtapChange(e.target.value)}
          >
            <MenuItem value="">Wszystkie</MenuItem>
            <MenuItem value="etap1">Etap I</MenuItem>
            <MenuItem value="etap2">Etap II</MenuItem>
            <MenuItem value="etap3">Etap III</MenuItem>
          </Select>
        </FormControl>

        <FormControlLabel
          control={
            <Checkbox
              checked={filters.showErrors}
              onChange={(e) => handleShowErrorsChange(e.target.checked)}
              size="small"
            />
          }
          label={
            <Typography variant="body2" color="text.secondary">
              Pokaż błędy systemowe
            </Typography>
          }
          sx={{ ml: 1 }}
        />

        {hasActiveFilters && (
          <Button
            size="small"
            startIcon={<ClearIcon />}
            onClick={handleClearFilters}
            sx={{ color: "text.secondary" }}
          >
            Wyczyść
          </Button>
        )}

        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ ml: { sm: "auto" } }}
        >
          {totalCount} {totalCount === 1 ? "rozwiązanie" : "rozwiązań"}
        </Typography>
      </Stack>
    </Paper>
  );
}
