"use client";

import { useCallback, useEffect, useState } from "react";
import { Alert, Box, Button, CircularProgress, LinearProgress, Paper, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { patternsApi } from "@/lib/api/patterns";
import { Pattern, ReviewCard, ReviewOutcome } from "@/lib/types";
import { PATTERN_LEVEL_NAMES, REVIEW_OUTCOMES } from "@/lib/utils/constants";
import { formatDay } from "./formatDay";

/**
 * solve: the exercise, solved on paper; check: solved - answer, solution and
 * the wzorzec shown, "was the wzorzec in it?"; recall / recalled: no exercise
 * yet, a plain card; rated: saved; failed: the card could not be loaded.
 */
type Stage = "loading" | "solve" | "check" | "recall" | "recalled" | "rated" | "failed" | "done";

/**
 * Today's queue, one card at a time: an exercise for the wzorzec, solved on
 * paper, then a two-step self-rating. A familiar wzorzec (level 2+) hides its
 * trigger; peeking caps the rating at "hard" on the server.
 */
export function ReviewSession() {
  const [queue, setQueue] = useState<Pattern[]>([]);
  const [index, setIndex] = useState(0);
  const [stage, setStage] = useState<Stage>("loading");
  const [card, setCard] = useState<ReviewCard | null>(null);
  const [peeked, setPeeked] = useState(false);
  const [result, setResult] = useState<Pattern | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const current = queue[index];

  const openCard = useCallback(async (pattern: Pattern | undefined) => {
    setResult(null);
    setError(null);
    setPeeked(false);
    if (!pattern) {
      setStage("done");
      return;
    }
    setStage("loading");
    try {
      const loaded = await patternsApi.card(pattern.id);
      setCard(loaded);
      setStage(loaded.exercise ? "solve" : "recall");
    } catch (e) {
      setCard(null);
      setError(e instanceof Error ? e.message : "Nie udało się wczytać karty.");
      setStage("failed");
    }
  }, []);

  useEffect(() => {
    patternsApi
      .queue(50)
      .then((data) => {
        setQueue(data.items);
        openCard(data.items[0]);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Nie udało się wczytać powtórek.");
        setStage("done");
      });
  }, [openCard]);

  const rate = async (outcome: ReviewOutcome) => {
    if (!current || !card) return;
    setBusy(true);
    setError(null);
    try {
      const { pattern } = await patternsApi.review(current.id, {
        outcome,
        exercise_id: card.exercise?.id ?? null,
        // A visible trigger was seen; a hidden one only if asked for
        trigger_shown: !card.trigger_hidden || peeked,
      });
      setResult(pattern);
      setStage("rated");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się zapisać powtórki.");
    } finally {
      setBusy(false);
    }
  };

  const skip = async () => {
    if (!current || !card?.exercise) return;
    setBusy(true);
    setError(null);
    try {
      await patternsApi.rejectExercise(current.id, card.exercise.id);
      await openCard(current);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się pominąć zadania.");
    } finally {
      setBusy(false);
    }
  };

  const next = () => {
    const nextIndex = index + 1;
    setIndex(nextIndex);
    openCard(queue[nextIndex]);
  };

  if (stage === "loading") {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress aria-label="Wczytywanie" />
      </Box>
    );
  }

  if (stage === "done" || !current) {
    return (
      <Paper sx={{ p: 4, textAlign: "center" }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <Typography variant="h6" sx={{ mb: 1 }}>Na dziś wszystko</Typography>
        <Typography sx={{ color: "grey.600", mb: 2 }}>
          {queue.length ? `Powtórzone wzorce: ${queue.length}.` : "Dziś nie ma wzorców do powtórki."}
        </Typography>
        <Button href="/wzorce" variant="outlined">Wróć do wzorców</Button>
      </Paper>
    );
  }

  const exercise = card?.exercise ?? null;
  // Solved or not, once rated (or past step 1) the whole wzorzec is shown
  const revealed = stage === "check" || stage === "recalled" || stage === "rated";
  const triggerVisible = !card?.trigger_hidden || peeked || revealed;

  return (
    <Box>
      <Box sx={{ mb: 2 }}>
        <Typography variant="body2" sx={{ color: "grey.600", mb: 0.5 }}>
          Karta {index + 1} z {queue.length}
        </Typography>
        <LinearProgress variant="determinate" value={(index / queue.length) * 100} />
      </Box>

      <Paper sx={{ p: 3 }} component="section" aria-label="Karta powtórki">
        <Box sx={{ display: "flex", gap: 1, mb: 2, flexWrap: "wrap" }}>
          {current.category && <CategoryBadge category={current.category} size="small" />}
          <Typography variant="caption" sx={{ color: "grey.600", alignSelf: "center" }}>
            {PATTERN_LEVEL_NAMES[current.level]}
          </Typography>
        </Box>

        {triggerVisible ? (
          <Box sx={{ mb: 2 }}>
            <Typography variant="overline" sx={{ color: "grey.600" }}>Kiedy w treści widzę…</Typography>
            <Box sx={{ fontSize: "1.15rem", fontWeight: 600 }} data-testid="review-trigger">
              <MathContent content={current.trigger} />
            </Box>
          </Box>
        ) : (
          <Button size="small" variant="outlined" sx={{ mb: 2 }} onClick={() => setPeeked(true)}>
            Pokaż, kiedy stosować ten wzorzec
          </Button>
        )}

        {exercise && (
          <Box sx={{ p: 2, mb: 2, bgcolor: "grey.50", borderRadius: 1 }} data-testid="review-exercise">
            <Typography variant="overline" sx={{ color: "grey.600" }}>Ćwiczenie</Typography>
            <Box sx={{ fontWeight: 600, mb: 1 }}>
              <MathContent content={exercise.title} />
            </Box>
            <MathContent content={exercise.content} />
          </Box>
        )}

        {stage === "failed" && (
          <Button variant="contained" onClick={next}>
            {index + 1 < queue.length ? "Następna karta" : "Zakończ"}
          </Button>
        )}

        {stage === "solve" && (
          <Box>
            <Typography variant="body2" sx={{ color: "grey.700", mb: 1.5 }}>
              Rozwiąż zadanie na kartce, a potem zaznacz, jak poszło.
            </Typography>
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: 1 }}>
              <Button variant="contained" onClick={() => setStage("check")} disabled={busy}>
                Zadanie zrobione
              </Button>
              <Button variant="outlined" color="error" onClick={() => rate("fail")} disabled={busy}>
                Zadanie nie zrobione
              </Button>
            </Box>
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
              <Button size="small" onClick={skip} disabled={busy}>
                Zadanie jest błędne - pomiń
              </Button>
              <Button size="small" href={`/wzorce/${current.id}/cwiczenia/druk`} target="_blank" rel="noopener">
                Wydrukuj ćwiczenia
              </Button>
            </Box>
          </Box>
        )}

        {stage === "recall" && (
          <Box>
            <Typography variant="body2" sx={{ color: "grey.700", mb: 1.5 }}>
              Ćwiczenia do tego wzorca jeszcze się układają. Przypomnij sobie, co warto wtedy spróbować.
            </Typography>
            <Button variant="contained" onClick={() => setStage("recalled")}>Pokaż wzorzec</Button>
          </Box>
        )}

        {revealed && (
          <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: exercise ? "1fr 1fr" : "1fr" }, mb: 2 }}>
            <Box sx={{ p: 2, bgcolor: "#f0fdf4", borderRadius: 1 }} data-testid="review-pattern">
              <Typography variant="caption" sx={{ color: "grey.600" }}>…to warto spróbować…</Typography>
              <MathContent content={current.action} />
              {current.example && (
                <Box sx={{ color: "grey.700", fontSize: "0.9rem", mt: 1 }}>
                  <MathContent content={`Przykład: ${current.example}`} />
                </Box>
              )}
            </Box>
            {exercise && (
              <Box sx={{ p: 2, bgcolor: "grey.50", borderRadius: 1 }}>
                <Typography variant="caption" sx={{ color: "grey.600" }}>Odpowiedź</Typography>
                <Box data-testid="review-answer">
                  <MathContent content={exercise.answer || "—"} />
                </Box>
                {exercise.solution && (
                  <>
                    <Typography variant="caption" component="div" sx={{ color: "grey.600", mt: 1.5 }}>
                      Rozwiązanie z tym wzorcem
                    </Typography>
                    <Box data-testid="review-solution">
                      <MathContent content={exercise.solution} />
                    </Box>
                  </>
                )}
              </Box>
            )}
          </Box>
        )}

        {stage === "check" && (
          <Box>
            <Typography sx={{ fontWeight: 600, mb: 1 }}>Czy ten wzorzec był w rozwiązaniu?</Typography>
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
              <Button variant="contained" color="success" onClick={() => rate("ok")} disabled={busy}>
                Tak, z tym wzorcem
              </Button>
              <Button variant="outlined" color="warning" onClick={() => rate("hard")} disabled={busy}>
                Inny sposób
              </Button>
              <Button variant="outlined" color="error" onClick={() => rate("fail")} disabled={busy}>
                Jednak nie zrobione
              </Button>
            </Box>
          </Box>
        )}

        {stage === "recalled" && (
          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
            <Button variant="outlined" color="error" onClick={() => rate("fail")} disabled={busy}>
              {REVIEW_OUTCOMES.fail}
            </Button>
            <Button variant="outlined" color="warning" onClick={() => rate("hard")} disabled={busy}>
              {REVIEW_OUTCOMES.hard}
            </Button>
            <Button variant="contained" color="success" onClick={() => rate("ok")} disabled={busy}>
              {REVIEW_OUTCOMES.ok}
            </Button>
          </Box>
        )}

        {stage === "rated" && result && (
          <Box>
            <Alert severity="success" sx={{ mb: 2 }}>
              {PATTERN_LEVEL_NAMES[result.level]} · następna powtórka {formatDay(result.due_on)}
            </Alert>
            <Button variant="contained" onClick={next}>
              {index + 1 < queue.length ? "Następna karta" : "Zakończ"}
            </Button>
          </Box>
        )}

        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      </Paper>
    </Box>
  );
}
