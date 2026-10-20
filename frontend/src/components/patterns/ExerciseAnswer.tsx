"use client";

import { useState } from "react";
import { Box, Button } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";

/** The short final answer of an exercise, hidden until asked for. */
export function ExerciseAnswer({ answer }: { answer: string }) {
  const [shown, setShown] = useState(false);
  return (
    <Box sx={{ mt: 2 }}>
      <Button size="small" onClick={() => setShown(!shown)} aria-expanded={shown}>
        {shown ? "Ukryj odpowiedź" : "Pokaż odpowiedź"}
      </Button>
      {shown && (
        <Box sx={{ mt: 1, p: 1.5, bgcolor: "grey.50", borderRadius: 1 }} data-testid="exercise-answer">
          <MathContent content={answer} />
        </Box>
      )}
    </Box>
  );
}
