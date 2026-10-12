"use client";

import { Box, Paper } from "@mui/material";
import { ReactNode } from "react";

interface FormCardProps {
  children: ReactNode;
  /** Wider card for lists (parent page) */
  wide?: boolean;
}

/**
 * Wycentrowana karta dla stron konta i rodzica. Na telefonie (360 px) karta
 * zajmuje cala szerokosc i ma mniejszy padding, zeby tresc sie miescila
 * bez przewijania w poziomie (WCAG 1.4.10).
 */
export function FormCard({ children, wide = false }: FormCardProps) {
  return (
    <Box sx={{ display: "flex", justifyContent: "center", minHeight: { sm: "50vh" } }}>
      <Paper
        sx={{
          p: { xs: 2.5, sm: 4 },
          width: "100%",
          maxWidth: wide ? 720 : 520,
          alignSelf: "flex-start",
          // Dlugie adresy e-mail i loginy lamia sie zamiast rozpychac karte
          overflowWrap: "anywhere",
        }}
      >
        {children}
      </Paper>
    </Box>
  );
}
