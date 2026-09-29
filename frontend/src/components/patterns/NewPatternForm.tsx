"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Alert, Box, Button, CircularProgress, Paper, Typography } from "@mui/material";
import { emptyDraft, patternsApi } from "@/lib/api/patterns";
import { PatternDraft, PatternSource, PatternVariant, RefineRound } from "@/lib/types";
import { PatternEditor, validatePattern } from "./PatternEditor";
import { RefinePanel } from "./RefinePanel";

interface NewPatternFormProps {
  source?: PatternSource | null;
  /** Human label of the source task, e.g. "2024 · etap1 · zad. 3" */
  sourceLabel?: string | null;
  /** A suggestion the student chose on the task page ("Podpowiedz wzorzec") */
  initialDraft?: PatternVariant | null;
}

export function NewPatternForm({ source, sourceLabel, initialDraft }: NewPatternFormProps) {
  const router = useRouter();
  const [draft, setDraft] = useState<PatternDraft>(
    initialDraft ? { ...emptyDraft(), ...initialDraft } : emptyDraft()
  );
  const [category, setCategory] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [rounds, setRounds] = useState<RefineRound[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pick = (variant: PatternVariant, round: RefineRound) => {
    setDraft({ ...draft, trigger: variant.trigger, action: variant.action, example: variant.example });
    if (round.category && !category) setCategory(round.category);
    if (round.skills?.length) setSkills(round.skills);
  };

  const onRoundsChange = (next: RefineRound[]) => {
    setRounds(next);
    const latest = next[next.length - 1];
    if (latest?.category && !category) setCategory(latest.category);
    if (latest?.skills?.length) setSkills(latest.skills);
  };

  const save = async () => {
    const problem = validatePattern(draft);
    if (problem) {
      setError(problem);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const { pattern } = await patternsApi.create({
        trigger: draft.trigger.trim(),
        action: draft.action.trim(),
        example: draft.example.trim() || undefined,
        category: category || null,
        skills,
        origin: initialDraft ? "ai_suggested" : "own",
        source: source ?? null,
        refinement: rounds.slice(-10),
      });
      router.push(`/wzorce/${pattern.id}?nowy=1`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się zapisać wzorca.");
      setSaving(false);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {sourceLabel && (
        <Alert severity="info">Wzorzec zostanie połączony z zadaniem: {sourceLabel}</Alert>
      )}
      {initialDraft && (
        <Alert severity="info">
          To propozycja AI. Przeczytaj ją, popraw po swojemu - zapamiętasz ją lepiej, jeśli będzie
          napisana Twoimi słowami.
        </Alert>
      )}
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" component="h2" sx={{ mb: 2 }}>
          Twój wzorzec
        </Typography>
        <PatternEditor
          value={draft}
          onChange={setDraft}
          category={category}
          onCategoryChange={setCategory}
          disabled={saving}
          showRaw={!initialDraft}
        />
      </Paper>

      <RefinePanel draft={draft} rounds={rounds} onRoundsChange={onRoundsChange} onPick={pick} source={source} />

      {error && <Alert severity="error">{error}</Alert>}
      <Box>
        <Button variant="contained" size="large" onClick={save} disabled={saving}
          startIcon={saving ? <CircularProgress size={18} color="inherit" /> : null}>
          Zapisz wzorzec
        </Button>
      </Box>
    </Box>
  );
}
