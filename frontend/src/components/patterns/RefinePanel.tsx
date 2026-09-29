"use client";

import { useState } from "react";
import { Alert, Box, Button, Chip, CircularProgress, Paper, TextField, Typography } from "@mui/material";
import { patternsApi } from "@/lib/api/patterns";
import { PatternDraft, PatternSource, PatternVariant, RefineRound } from "@/lib/types";
import { PATTERN_ANSWER_MAX, PATTERN_VERDICTS } from "@/lib/utils/constants";
import { canRefine } from "./PatternEditor";
import { VariantCard } from "./VariantCard";

interface RefinePanelProps {
  draft: PatternDraft;
  rounds: RefineRound[];
  onRoundsChange: (rounds: RefineRound[]) => void;
  /** Called when the student picks a version (loads it into the editor) */
  onPick: (variant: PatternVariant, round: RefineRound) => void;
  source?: PatternSource | null;
  /** Refining a saved pattern: the server adds its source and stored rounds */
  patternId?: string;
}

/**
 * Guided refine rounds with the AI: each round offers 2-3 versions to pick
 * from, a verdict and up to two questions the student can answer before
 * asking for the next round.
 */
export function RefinePanel({ draft, rounds, onRoundsChange, onPick, source, patternId }: RefinePanelProps) {
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const last = rounds[rounds.length - 1];

  const ask = async () => {
    if (!canRefine(draft)) {
      setError("Napisz najpierw swój pomysł - jednym zdaniem albo jako wyzwalacz i akcję.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { round } = await patternsApi.refine({
        draft,
        source: patternId ? undefined : source,
        history: rounds,
        answer: answer.trim() || null,
        pattern_id: patternId,
      });
      onRoundsChange([...rounds, { ...round, chosen: null }]);
      setAnswer("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Wystąpił błąd.");
    } finally {
      setBusy(false);
    }
  };

  const pick = (roundIndex: number, variantIndex: number) => {
    const updated = rounds.map((r, i) => (i === roundIndex ? { ...r, chosen: variantIndex } : r));
    onRoundsChange(updated);
    onPick(rounds[roundIndex].variants[variantIndex], updated[roundIndex]);
  };

  return (
    <Paper sx={{ p: 3 }} component="section" aria-label="Dopracuj z AI">
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
        Dopracuj z AI
      </Typography>
      <Typography variant="body2" sx={{ color: "grey.600", mb: 2 }}>
        AI zaproponuje kilka wersji Twojego wzorca i może zadać pytanie. Wybierz wersję, popraw ją
        po swojemu albo odpowiedz i poproś o kolejną rundę.
      </Typography>

      {rounds.map((round, roundIndex) => {
        const verdict = PATTERN_VERDICTS[round.verdict] ?? PATTERN_VERDICTS.ok;
        const isLast = roundIndex === rounds.length - 1;
        return (
          <Box key={roundIndex} sx={{ mb: 3, opacity: isLast ? 1 : 0.75 }} data-testid="refine-round">
            <Box sx={{ display: "flex", gap: 1, alignItems: "center", mb: 1, flexWrap: "wrap" }}>
              <Typography variant="subtitle2">Runda {roundIndex + 1}</Typography>
              <Chip size="small" color={verdict.color} label={verdict.label} />
            </Box>
            {round.comment && (
              <Typography variant="body2" sx={{ mb: 1.5, color: "grey.800" }}>
                {round.comment}
              </Typography>
            )}
            <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" } }}>
              {round.variants.map((variant, variantIndex) => (
                <VariantCard
                  key={variantIndex}
                  variant={variant}
                  label={`Wersja ${variantIndex + 1}`}
                  chosen={round.chosen === variantIndex}
                  onChoose={() => pick(roundIndex, variantIndex)}
                  disabled={busy}
                />
              ))}
            </Box>
            {isLast && round.questions.length > 0 && (
              <Box sx={{ mt: 2, p: 2, bgcolor: "#eff6ff", borderRadius: 1 }}>
                <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                  Pytania od AI
                </Typography>
                <Box component="ul" sx={{ m: 0, pl: 3 }}>
                  {round.questions.map((q, i) => (
                    <li key={i}>
                      <Typography variant="body2">{q}</Typography>
                    </li>
                  ))}
                </Box>
              </Box>
            )}
          </Box>
        );
      })}

      {last && (
        <TextField
          id="refine-answer"
          label={last.questions.length ? "Twoja odpowiedź (opcjonalnie)" : "Uwagi do kolejnej rundy (opcjonalnie)"}
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          disabled={busy}
          multiline
          fullWidth
          sx={{ mb: 2 }}
          slotProps={{ htmlInput: { maxLength: PATTERN_ANSWER_MAX } }}
        />
      )}

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Button variant="outlined" onClick={ask} disabled={busy} startIcon={busy ? <CircularProgress size={16} /> : null}>
        {busy ? "AI myśli…" : rounds.length ? "Kolejna runda" : "Dopracuj z AI"}
      </Button>
    </Paper>
  );
}
