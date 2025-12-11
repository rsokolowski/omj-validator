"use client";

import { useState, useEffect, useCallback } from "react";
import { Autocomplete, TextField, Box, Typography } from "@mui/material";
import { fetchAPI } from "@/lib/api/client";
import { AdminUser, AdminUsersSearchResponse } from "@/lib/types";

interface UserAutocompleteProps {
  value: AdminUser | null;
  onChange: (user: AdminUser | null) => void;
}

export function UserAutocomplete({ value, onChange }: UserAutocompleteProps) {
  const [inputValue, setInputValue] = useState("");
  const [options, setOptions] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(false);

  const searchUsers = useCallback(async (query: string) => {
    if (!query) {
      setOptions([]);
      return;
    }

    setLoading(true);
    try {
      const response = await fetchAPI<AdminUsersSearchResponse>(
        `/api/admin/users/search?q=${encodeURIComponent(query)}&limit=10`
      );
      setOptions(response.users);
    } catch (error) {
      console.error("Failed to search users:", error);
      setOptions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      searchUsers(inputValue);
    }, 300);

    return () => clearTimeout(timer);
  }, [inputValue, searchUsers]);

  return (
    <Autocomplete
      value={value}
      onChange={(_, newValue) => onChange(newValue)}
      inputValue={inputValue}
      onInputChange={(_, newInputValue) => setInputValue(newInputValue)}
      options={options}
      loading={loading}
      getOptionLabel={(option) => option.email}
      isOptionEqualToValue={(option, value) => option.google_sub === value.google_sub}
      filterOptions={(x) => x} // Disable client-side filtering (server handles it)
      renderOption={(props, option) => {
        const { key, ...rest } = props;
        return (
          <Box component="li" key={key} {...rest} sx={{ display: "flex", flexDirection: "column", alignItems: "flex-start !important" }}>
            <Typography variant="body2">{option.email}</Typography>
            {option.name && (
              <Typography variant="caption" color="text.secondary">
                {option.name}
              </Typography>
            )}
          </Box>
        );
      }}
      renderInput={(params) => (
        <TextField
          {...params}
          label="Filter by user"
          placeholder="Type email to search..."
          size="small"
          sx={{ minWidth: 250 }}
        />
      )}
      noOptionsText={inputValue ? "No users found" : "Type to search users"}
    />
  );
}
