"use client";

import { useState } from "react";
import { Alert, Box, Button, CircularProgress, Paper, Typography } from "@mui/material";
import { patternsApi } from "@/lib/api/patterns";
import { ExerciseBatch, ExerciseSummary } from "@/lib/types";
import { ExerciseList } from "./ExerciseList";
import { useExerciseBatches } from "./ExerciseBatchProvider";

interface Props {
  patternId: string;
  exercises: ExerciseSummary[];
  batch: ExerciseBatch | null;
}

/** "Ćwiczenia" on a wzorzec page: the drills, progress of a batch, print and "more". */
export function ExercisesSection({ patternId, exercises, batch }: Props) {
  const { running, track } = useExerciseBatches();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isRunning =
    batch?.status === "running" || running.some((b) => b.pattern_id === patternId);
  const failed = !isRunning && batch?.status === "failed" ? batch : null;

  const generate = async () => {
    setStarting(true);
    setError(null);
    try {
      const { batch: started } = await patternsApi.generateExercises(patternId);
      track(started);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się zacząć układania ćwiczeń.");
    } finally {
      setStarting(false);
    }
  };

  return (
    <Paper sx={{ p: 3 }} component="section" aria-label="Ćwiczenia">
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
        Ćwiczenia
      </Typography>
      <Typography variant="body2" sx={{ color: "grey.600", mb: 2 }}>
        Krótkie zadania, w których ten wzorzec wystarcza do rozwiązania - od łatwych do średnich.
      </Typography>

      {isRunning && (
        <Alert severity="info" icon={<CircularProgress size={18} />} sx={{ mb: 2 }} data-testid="exercises-running">
          Układam 5 ćwiczeń do tego wzorca… Możesz w tym czasie robić coś innego, dam znać.
        </Alert>
      )}
      {failed && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {failed.message ?? "Nie udało się ułożyć ćwiczeń. Spróbuj ponownie."}
        </Alert>
      )}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {exercises.length > 0 ? (
        <ExerciseList exercises={exercises} />
      ) : (
        !isRunning && (
          <Typography variant="body2" sx={{ color: "grey.700", mb: 1 }}>
            Ten wzorzec nie ma jeszcze ćwiczeń.
          </Typography>
        )
      )}

      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mt: 2 }}>
        {exercises.length > 0 && (
          <Button variant="outlined" size="small" href={`/wzorce/${patternId}/cwiczenia/druk`}>
            Drukuj / PDF
          </Button>
        )}
        <Button variant="outlined" size="small" onClick={generate} disabled={isRunning || starting}>
          {failed ? "Spróbuj ponownie" : exercises.length > 0 ? "Wygeneruj 5 kolejnych" : "Wygeneruj ćwiczenia"}
        </Button>
      </Box>
      {exercises.length > 0 && (
        <Typography variant="caption" component="p" sx={{ color: "grey.600", mt: 1 }}>
          Ćwiczenia są zapisane w Moich zadaniach - tam też możesz przesłać rozwiązanie do oceny.
        </Typography>
      )}
    </Paper>
  );
}
