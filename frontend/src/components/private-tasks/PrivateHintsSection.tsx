"use client";

import { useState } from "react";
import { Alert, Box, Button, Paper, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { AiGeneratedNotice } from "@/components/ui/AiGeneratedNotice";
import { fetchAPI } from "@/lib/api/client";
import { RevealHintResponse } from "@/lib/types";

interface PrivateHintsSectionProps {
  taskId: string;
  hintsCount: number;
  initialRevealed: string[];
}

/**
 * Hints of a private task, fetched one at a time. The server records how many
 * were revealed before the next submission, so "solved with a hint" is honest.
 */
export function PrivateHintsSection({ taskId, hintsCount, initialRevealed }: PrivateHintsSectionProps) {
  const [revealed, setRevealed] = useState<string[]>(initialRevealed);
  const [visible, setVisible] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const showNext = async () => {
    const n = visible + 1;
    setError(null);
    if (n <= revealed.length) {
      // Already revealed earlier - the server still records it as used
      setVisible(n);
    }
    setLoading(true);
    try {
      const result = await fetchAPI<RevealHintResponse>(`/api/private-tasks/${taskId}/hints/${n}`, {
        method: "POST",
      });
      setRevealed((prev) => {
        const next = [...prev];
        next[n - 1] = result.hint;
        return next;
      });
      setVisible(n);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się pobrać wskazówki.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 1,
          mb: 2,
          pb: 1.5,
          borderBottom: 1,
          borderColor: "grey.200",
        }}
      >
        <Typography variant="h6" component="h2" sx={{ color: "grey.700" }}>
          Wskazówki ({visible}/{hintsCount})
        </Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          {visible > 0 && (
            <Button size="small" variant="outlined" onClick={() => setVisible(0)}>
              Ukryj wszystkie
            </Button>
          )}
          {visible < hintsCount && (
            <Button size="small" variant="contained" onClick={showNext} disabled={loading}>
              Pokaż wskazówkę {visible + 1}
            </Button>
          )}
        </Box>
      </Box>

      <AiGeneratedNotice variant="hints" style={{ marginBottom: "12px" }} />
      <Typography variant="body2" sx={{ color: "grey.600", mb: 2 }}>
        Odkrycie wskazówki zostanie zapisane przy Twoim następnym rozwiązaniu.
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }} aria-live="polite">
        {revealed.slice(0, visible).map((hint, index) => (
          <Box
            key={index}
            sx={{ p: 2, borderRadius: 1, borderLeft: 4, borderColor: "warning.main", backgroundColor: "#fffbeb" }}
          >
            <Typography variant="caption" sx={{ color: "grey.600", display: "block", mb: 0.5 }}>
              Wskazówka {index + 1}
            </Typography>
            <MathContent content={hint} />
          </Box>
        ))}
      </Box>
    </Paper>
  );
}
