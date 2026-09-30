"use client";

import { useEffect, useRef, useState } from "react";
import { Alert, Box, Button, Chip, CircularProgress, Paper, TextField, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { patternsApi } from "@/lib/api/patterns";
import { PatternDraft, PatternSource, PatternVariant, RefineRound } from "@/lib/types";
import { PATTERN_ANSWER_MAX, PATTERN_MESSAGE_MAX, PATTERN_VERDICTS } from "@/lib/utils/constants";
import { canRefine } from "./PatternEditor";
import { TextWithTasks } from "./TaskChip";
import { VariantCard } from "./VariantCard";

interface RefinePanelProps {
  draft: PatternDraft;
  rounds: RefineRound[];
  onRoundsChange: (rounds: RefineRound[]) => void;
  /** Called when the student picks a version (loads it into the editor) */
  onPick: (variant: PatternVariant, round: RefineRound, rounds: RefineRound[]) => void;
  source?: PatternSource | null;
  /** The editor's category - narrows the OMJ tasks the AI can point to */
  category?: string | null;
  /** Refining a saved pattern: the server adds its source and stored rounds */
  patternId?: string;
  /** Rounds saved with the pattern, shown read-only above this session */
  earlierRounds?: RefineRound[];
}

/**
 * A conversation with the AI about one pattern. Each turn the student may
 * answer the AI's questions (one field per question) and write their own
 * message; the AI replies, offers 2-3 versions from broadest to narrowest,
 * each with OMJ tasks where it helps, rates the current draft and may ask
 * questions back.
 */
export function RefinePanel({
  draft, rounds, onRoundsChange, onPick, source, category, patternId, earlierRounds = [],
}: RefinePanelProps) {
  const [answers, setAnswers] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showEarlier, setShowEarlier] = useState(false);
  const lastRoundRef = useRef<HTMLDivElement>(null);
  const last = rounds[rounds.length - 1];

  useEffect(() => {
    if (rounds.length) lastRoundRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [rounds.length]);

  const send = async () => {
    if (!canRefine(draft)) {
      setError("Napisz najpierw swój pomysł - jednym zdaniem albo jako wyzwalacz i akcję.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const questions = last?.questions ?? [];
      const { round } = await patternsApi.refine({
        draft,
        source: patternId ? undefined : source,
        history: rounds.slice(-10),
        answers: questions.map((_, i) => answers[i]?.trim() || null),
        message: message.trim() || null,
        category: category || null,
        pattern_id: patternId,
      });
      onRoundsChange([...rounds, { ...round, chosen: null }]);
      setAnswers([]);
      setMessage("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Wystąpił błąd.");
    } finally {
      setBusy(false);
    }
  };

  const pick = (roundIndex: number, variantIndex: number) => {
    const updated = rounds.map((r, i) => (i === roundIndex ? { ...r, chosen: variantIndex } : r));
    onRoundsChange(updated);
    onPick(rounds[roundIndex].variants[variantIndex], updated[roundIndex], updated);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && !busy) {
      e.preventDefault();
      send();
    }
  };

  return (
    <Paper sx={{ p: 3 }} component="section" aria-label="Dopracuj z AI">
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
        Dopracuj z AI
      </Typography>
      <Typography variant="body2" sx={{ color: "grey.600", mb: 2 }}>
        Rozmawiasz z AI o swoim wzorcu - pamięta całą rozmowę i widzi {patternId ? "zapisany wzorzec" : "Twój aktualny szkic z formularza"}.
        Pisz, co myślisz, pytaj, proś o przykłady zadań. Każda wersja pokazuje zadania OMJ, w których
        pomaga - po tym poznasz, czy wzorzec jest wystarczająco ogólny.
      </Typography>

      {earlierRounds.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Button size="small" onClick={() => setShowEarlier(!showEarlier)}>
            {showEarlier ? "Ukryj wcześniejszą rozmowę" : `Pokaż wcześniejszą rozmowę (${earlierRounds.length})`}
          </Button>
          {showEarlier && (
            <Box sx={{ mt: 1, opacity: 0.75 }}>
              {earlierRounds.map((round, i) => (
                <Turn key={i} round={round} previous={earlierRounds[i - 1]} number={i + 1} />
              ))}
            </Box>
          )}
        </Box>
      )}

      {rounds.map((round, roundIndex) => {
        const isLast = roundIndex === rounds.length - 1;
        return (
          <Box key={roundIndex} ref={isLast ? lastRoundRef : undefined} sx={{ scrollMarginTop: 80 }}>
            <Turn
              round={round}
              previous={rounds[roundIndex - 1]}
              number={earlierRounds.length + roundIndex + 1}
              faded={!isLast}
              busy={busy}
              onPick={(variantIndex) => pick(roundIndex, variantIndex)}
              answers={isLast ? answers : undefined}
              onAnswer={isLast ? (i, value) => {
                const next = [...answers];
                next[i] = value;
                setAnswers(next);
              } : undefined}
              onKeyDown={onKeyDown}
            />
          </Box>
        );
      })}

      <TextField
        id="refine-message"
        label={rounds.length ? "Napisz do AI (opcjonalnie)" : "Coś do dodania? (opcjonalnie)"}
        placeholder="Np. „dlaczego za ogólny?”, „wersja 2, ale bardziej ogólnie”, „podaj zadania z II etapu”"
        helperText="Ctrl+Enter wysyła"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={busy}
        multiline
        minRows={2}
        fullWidth
        sx={{ mb: 2 }}
        slotProps={{ htmlInput: { maxLength: PATTERN_MESSAGE_MAX } }}
      />

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Button variant="contained" onClick={send} disabled={busy} startIcon={busy ? <CircularProgress size={16} /> : null}>
        {busy ? "AI myśli…" : rounds.length ? "Wyślij" : "Dopracuj z AI"}
      </Button>
    </Paper>
  );
}

interface TurnProps {
  round: RefineRound;
  /** The round before - its questions are what this round's answers reply to */
  previous?: RefineRound;
  number: number;
  faded?: boolean;
  busy?: boolean;
  onPick?: (variantIndex: number) => void;
  /** Present on the latest round: one answer field per question */
  answers?: string[];
  onAnswer?: (index: number, value: string) => void;
  onKeyDown?: (e: React.KeyboardEvent) => void;
}

/** One exchange: what the student sent, then the AI's reply, versions and questions. */
function Turn({ round, previous, number, faded, busy, onPick, answers, onAnswer, onKeyDown }: TurnProps) {
  const verdict = PATTERN_VERDICTS[round.verdict] ?? PATTERN_VERDICTS.ok;
  const askedBefore = previous?.questions ?? [];
  const answered = askedBefore
    .map((question, i) => ({ question, answer: round.answers?.[i] }))
    .filter((pair) => pair.answer);
  const studentSaid = answered.length > 0 || round.message || round.answer;

  return (
    <Box sx={{ mb: 3, opacity: faded ? 0.8 : 1 }} data-testid="refine-round">
      {studentSaid && (
        <Box sx={{ display: "flex", justifyContent: "flex-end", mb: 1.5 }}>
          <Box sx={{ maxWidth: "85%", bgcolor: "grey.100", borderRadius: 2, px: 2, py: 1.5 }}>
            <Typography variant="caption" sx={{ color: "grey.600", fontWeight: 600 }}>Ty</Typography>
            {answered.map((pair, i) => (
              <Box key={i} sx={{ mt: 0.5 }}>
                <Typography variant="caption" component="div" sx={{ color: "grey.600" }}>
                  <MathContent content={`Na pytanie: ${pair.question}`} />
                </Typography>
                <Typography variant="body2" component="div">
                  <MathContent content={pair.answer ?? ""} />
                </Typography>
              </Box>
            ))}
            {(round.message || round.answer) && (
              <Typography variant="body2" component="div" sx={{ mt: 0.5, whiteSpace: "pre-wrap" }}>
                <MathContent content={round.message || round.answer || ""} />
              </Typography>
            )}
          </Box>
        </Box>
      )}

      <Box sx={{ borderLeft: 3, borderColor: "primary.light", pl: 2 }}>
        <Typography variant="subtitle2" sx={{ mb: 1 }}>AI · runda {number}</Typography>

        {round.reply && (
          <Typography variant="body1" component="div" sx={{ mb: 1.5, whiteSpace: "pre-wrap" }}>
            <TextWithTasks text={round.reply} />
          </Typography>
        )}

        <Box sx={{ display: "flex", gap: 1, alignItems: "center", mb: 1.5, flexWrap: "wrap" }}>
          <Typography variant="body2" sx={{ color: "grey.600" }}>Twój szkic:</Typography>
          <Chip size="small" color={verdict.color} label={verdict.label} />
          {round.comment && (
            <Typography variant="body2" component="div" sx={{ color: "grey.800", flexBasis: "100%" }}>
              <TextWithTasks text={round.comment} />
            </Typography>
          )}
        </Box>

        <Typography variant="caption" sx={{ color: "grey.600", display: "block", mb: 0.5 }}>
          Wersje do wyboru - od najszerszej do najwęższej. Wybrana trafia do formularza, możesz ją poprawić i rozmawiać dalej.
        </Typography>
        <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" } }}>
          {round.variants.map((variant, variantIndex) => (
            <VariantCard
              key={variantIndex}
              variant={variant}
              label={`Wersja ${variantIndex + 1}`}
              chosen={round.chosen === variantIndex}
              onChoose={onPick ? () => onPick(variantIndex) : undefined}
              disabled={busy}
            />
          ))}
        </Box>

        {round.questions.length > 0 && (
          <Box sx={{ mt: 2, p: 2, bgcolor: "#eff6ff", borderRadius: 1, display: "flex", flexDirection: "column", gap: 1.5 }}>
            <Typography variant="subtitle2">Pytania od AI{onAnswer ? " - odpowiedz, jeśli chcesz" : ""}</Typography>
            {round.questions.map((question, i) => (
              <Box key={i}>
                <Typography variant="body2" component="div" sx={{ mb: onAnswer ? 0.5 : 0 }}>
                  <TextWithTasks text={`${i + 1}. ${question}`} />
                </Typography>
                {onAnswer && (
                  <TextField
                    size="small"
                    label={`Odpowiedź na pytanie ${i + 1}`}
                    value={answers?.[i] ?? ""}
                    onChange={(e) => onAnswer(i, e.target.value)}
                    onKeyDown={onKeyDown}
                    disabled={busy}
                    multiline
                    fullWidth
                    sx={{ bgcolor: "white" }}
                    slotProps={{ htmlInput: { maxLength: PATTERN_ANSWER_MAX } }}
                  />
                )}
              </Box>
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
}
