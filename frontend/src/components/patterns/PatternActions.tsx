"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Paper,
} from "@mui/material";
import { patternsApi } from "@/lib/api/patterns";
import { PatternDetail, PatternDraft, PatternVariant, RefineRound } from "@/lib/types";
import { PatternEditor, validatePattern } from "./PatternEditor";
import { RefinePanel } from "./RefinePanel";

function toDraft(pattern: PatternDetail): PatternDraft {
  return { trigger: pattern.trigger, action: pattern.action, example: pattern.example ?? "", raw: "" };
}

/** Edit, refine with the AI, pause/resume and delete a saved pattern. */
export function PatternActions({ pattern }: { pattern: PatternDetail }) {
  const router = useRouter();
  const [mode, setMode] = useState<"idle" | "edit" | "refine">("idle");
  const [draft, setDraft] = useState<PatternDraft>(toDraft(pattern));
  const [category, setCategory] = useState(pattern.category ?? "");
  const [rounds, setRounds] = useState<RefineRound[]>([]);
  const [deleting, setDeleting] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Wystąpił błąd.");
    } finally {
      setBusy(false);
    }
  };

  const save = () => {
    const problem = validatePattern(draft);
    if (problem) {
      setError(problem);
      return;
    }
    run(async () => {
      await patternsApi.update(pattern.id, {
        trigger: draft.trigger.trim(),
        action: draft.action.trim(),
        example: draft.example.trim(),
        category: category || null,
      });
      setMode("idle");
      router.refresh();
    });
  };

  // Picking a version saves it right away, with the conversation that led to it
  const pick = (variant: PatternVariant, _round: RefineRound, session: RefineRound[]) =>
    run(async () => {
      await patternsApi.update(pattern.id, {
        trigger: variant.trigger,
        action: variant.action,
        example: variant.example,
        append_rounds: session,
      });
      setDraft({ ...draft, trigger: variant.trigger, action: variant.action, example: variant.example });
      setRounds([]);
      setMode("idle");
      router.refresh();
    });

  const toggleArchive = () =>
    run(async () => {
      await patternsApi.update(pattern.id, { archived: !pattern.archived });
      router.refresh();
    });

  const remove = () =>
    run(async () => {
      await patternsApi.remove(pattern.id);
      router.push("/wzorce");
      router.refresh();
    });

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
        <Button size="small" variant={mode === "refine" ? "contained" : "outlined"}
          onClick={() => setMode(mode === "refine" ? "idle" : "refine")} disabled={busy}>
          Dopracuj z AI
        </Button>
        <Button size="small" variant={mode === "edit" ? "contained" : "outlined"}
          onClick={() => setMode(mode === "edit" ? "idle" : "edit")} disabled={busy}>
          Edytuj
        </Button>
        <Button size="small" onClick={toggleArchive} disabled={busy}>
          {pattern.archived ? "Wznów powtórki" : "Wstrzymaj powtórki"}
        </Button>
        <Button size="small" color="error" onClick={() => setDeleting(true)} disabled={busy}>
          Usuń
        </Button>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      {mode === "edit" && (
        <Paper sx={{ p: 3 }}>
          <PatternEditor value={draft} onChange={setDraft} category={category} onCategoryChange={setCategory} disabled={busy} />
          <Box sx={{ mt: 2, display: "flex", gap: 1 }}>
            <Button variant="contained" onClick={save} disabled={busy}>Zapisz</Button>
            <Button onClick={() => setMode("idle")} disabled={busy}>Anuluj</Button>
          </Box>
        </Paper>
      )}

      {mode === "refine" && (
        <RefinePanel draft={draft} rounds={rounds} onRoundsChange={setRounds} onPick={pick} patternId={pattern.id}
          category={category} earlierRounds={pattern.refinement} />
      )}

      <Dialog open={deleting} onClose={() => setDeleting(false)}>
        <DialogTitle>Usunąć wzorzec?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Wzorzec zniknie razem z historią powtórek i listą zadań. Twoje rozwiązania zadań zostaną.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleting(false)}>Anuluj</Button>
          <Button color="error" onClick={remove} disabled={busy}>Usuń</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
