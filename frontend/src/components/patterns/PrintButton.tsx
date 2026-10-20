"use client";

import { Button } from "@mui/material";

/** Opens the browser's print dialog ("Zapisz jako PDF" works there too). */
export function PrintButton() {
  return (
    <Button variant="contained" onClick={() => window.print()}>
      Drukuj / zapisz PDF
    </Button>
  );
}
