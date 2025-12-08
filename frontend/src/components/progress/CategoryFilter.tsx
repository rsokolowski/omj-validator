"use client";

import { useRouter } from "next/navigation";
import { Box, Chip, Paper, Typography } from "@mui/material";
import { CATEGORY_NAMES } from "@/lib/utils/constants";

interface CategoryFilterProps {
  currentCategory?: string;
}

export function CategoryFilter({ currentCategory }: CategoryFilterProps) {
  const router = useRouter();

  const categories = Object.entries(CATEGORY_NAMES);

  const handleCategoryClick = (category: string | null) => {
    if (category) {
      router.push(`/progress?category=${category}`);
    } else {
      router.push("/progress");
    }
  };

  return (
    <Paper sx={{ p: 2, mb: 3 }}>
      <Typography variant="subtitle2" sx={{ color: "grey.600", mb: 1.5 }}>
        Filtruj według kategorii:
      </Typography>
      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1 }}>
        <Chip
          label="Wszystkie"
          size="small"
          onClick={() => handleCategoryClick(null)}
          sx={{
            bgcolor: !currentCategory ? "primary.main" : "grey.100",
            color: !currentCategory ? "white" : "grey.700",
            "&:hover": {
              bgcolor: !currentCategory ? "primary.dark" : "grey.200",
            },
          }}
        />
        {categories.map(([key, name]) => (
          <Chip
            key={key}
            label={name}
            size="small"
            onClick={() => handleCategoryClick(key)}
            sx={{
              bgcolor: currentCategory === key ? "primary.main" : "grey.100",
              color: currentCategory === key ? "white" : "grey.700",
              "&:hover": {
                bgcolor: currentCategory === key ? "primary.dark" : "grey.200",
              },
            }}
          />
        ))}
      </Box>
    </Paper>
  );
}
