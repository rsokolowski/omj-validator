"use client";

import { useState } from "react";
import { Box, Button, Collapse } from "@mui/material";

export function SourcePhotos({ photos }: { photos: string[] }) {
  const [open, setOpen] = useState(false);
  if (!photos.length) return null;
  return (
    <Box sx={{ mt: 2 }}>
      <Button
        size="small"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls="zdjecia-zadania"
      >
        {open ? "Ukryj zdjęcie zadania" : "Pokaż zdjęcie zadania"}
      </Button>
      <Collapse in={open}>
        <Box id="zdjecia-zadania" sx={{ display: "flex", gap: 1, flexWrap: "wrap", mt: 1 }}>
          {photos.map((photo, i) => (
            <a key={photo} href={`/uploads/${photo}`} target="_blank" rel="noopener noreferrer">
              <Box
                component="img"
                src={`/uploads/${photo}`}
                alt={`Zdjęcie zadania ${i + 1} z ${photos.length} — otwiera się w nowej karcie`}
                sx={{ maxHeight: 240, maxWidth: "100%", borderRadius: 1, border: 1, borderColor: "grey.200" }}
              />
            </a>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}
