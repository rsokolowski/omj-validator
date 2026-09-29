"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Alert, Box, Button, CircularProgress, LinearProgress, Paper, TextField, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { patternsApi } from "@/lib/api/patterns";
import { Pattern, PracticeTask } from "@/lib/types";
import { PATTERN_LEVEL_NAMES, RECALL_TEXT_MAX, RECALL_TEXT_MIN, REVIEW_OUTCOMES } from "@/lib/utils/constants";
import { formatDay } from "./formatDay";

type Stage = "loading" | "practice" | "recall" | "revealed" | "rated" | "done";

/**
 * Today's queue, one card at a time. A card may offer a linked task to solve
 * (graded, counts as the review); otherwise the student types the action from
 * memory, compares it with the saved pattern and rates himself.
 */
export function ReviewSession() {
  const [queue, setQueue] = useState<Pattern[]>([]);
  const [index, setIndex] = useState(0);
  const [stage, setStage] = useState<Stage>("loading");
  const [practice, setPractice] = useState<PracticeTask | null>(null);
  const [recall, setRecall] = useState("");
  const [result, setResult] = useState<Pattern | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const current = queue[index];

  const openCard = useCallback(async (pattern: Pattern | undefined) => {
    setRecall("");
    setResult(null);
    setError(null);
    if (!pattern) {
      setStage("done");
      return;
    }
    setStage("loading");
    try {
      const { task } = await patternsApi.practice(pattern.id);
      setPractice(task);
      setStage(task ? "practice" : "recall");
    } catch {
      setPractice(null);
      setStage("recall");
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

  const rate = async (outcome: "fail" | "hard" | "ok") => {
    if (!current) return;
    setBusy(true);
    setError(null);
    try {
      const { pattern } = await patternsApi.review(current.id, recall.trim(), outcome);
      setResult(pattern);
      setStage("rated");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Nie udało się zapisać powtórki.");
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

  const recallTooShort = recall.trim().length < RECALL_TEXT_MIN;

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
        <Typography variant="overline" sx={{ color: "grey.600" }}>Kiedy w treści widzę…</Typography>
        <Box sx={{ fontSize: "1.15rem", fontWeight: 600, mb: 2 }}>
          <MathContent content={current.trigger} />
        </Box>

        {stage === "practice" && practice && (
          <Box>
            <Alert severity="info" sx={{ mb: 2 }}>
              Zamiast przypominania rozwiąż zadanie, w którym ten wzorzec się przydaje. Ocena
              rozwiązania zaliczy się jako powtórka.
            </Alert>
            <Box sx={{ mb: 2, fontWeight: 600 }}>
              <MathContent content={practice.title} />
            </Box>
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
              <Button variant="contained" component={Link} href={`${practice.url}?wzorzec=${current.id}`}>
                Rozwiąż zadanie
              </Button>
              <Button onClick={() => setStage("recall")}>Wolę szybką powtórkę</Button>
            </Box>
          </Box>
        )}

        {stage === "recall" && (
          <Box>
            <TextField
              id="recall-text"
              label="…to warto spróbować… (napisz z pamięci)"
              value={recall}
              onChange={(e) => setRecall(e.target.value)}
              multiline
              minRows={3}
              fullWidth
              autoFocus
              slotProps={{ htmlInput: { maxLength: RECALL_TEXT_MAX } }}
              helperText={recallTooShort ? `Co najmniej ${RECALL_TEXT_MIN} znaków - choćby jedno zdanie.` : " "}
            />
            <Button sx={{ mt: 1 }} variant="contained" onClick={() => setStage("revealed")} disabled={recallTooShort}>
              Pokaż
            </Button>
          </Box>
        )}

        {(stage === "revealed" || stage === "rated") && (
          <Box>
            <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, mb: 2 }}>
              <Box sx={{ p: 2, bgcolor: "grey.50", borderRadius: 1 }}>
                <Typography variant="caption" sx={{ color: "grey.600" }}>Twoja odpowiedź</Typography>
                <Typography sx={{ whiteSpace: "pre-wrap" }}>{recall}</Typography>
              </Box>
              <Box sx={{ p: 2, bgcolor: "#f0fdf4", borderRadius: 1 }}>
                <Typography variant="caption" sx={{ color: "grey.600" }}>Zapisany wzorzec</Typography>
                <MathContent content={current.action} />
                {current.example && (
                  <Box sx={{ color: "grey.700", fontSize: "0.9rem", mt: 1 }}>
                    <MathContent content={`Przykład: ${current.example}`} />
                  </Box>
                )}
              </Box>
            </Box>

            {stage === "revealed" && (
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
          </Box>
        )}

        {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      </Paper>
    </Box>
  );
}
