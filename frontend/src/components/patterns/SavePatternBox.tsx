"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Alert, Box, Button, CircularProgress, Paper, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { patternsApi } from "@/lib/api/patterns";
import { Pattern, PatternSource, PatternSuggestion } from "@/lib/types";
import { VariantCard } from "./VariantCard";

interface SavePatternBoxProps {
  source: PatternSource;
  /** Latest graded submission of this task - "Podpowiedz wzorzec" reads its feedback */
  latestSubmissionId?: string | null;
}

function sourceQuery(source: PatternSource): string {
  return source.task_key
    ? `task=${encodeURIComponent(source.task_key)}`
    : `private=${encodeURIComponent(source.private_task_id ?? "")}`;
}

/**
 * Under a graded task: save a pattern noticed while solving it, or ask the AI
 * what is worth remembering. Also lists the student's patterns linked here.
 */
export function SavePatternBox({ source, latestSubmissionId }: SavePatternBoxProps) {
  const router = useRouter();
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [suggestions, setSuggestions] = useState<PatternSuggestion[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    patternsApi
      .forTask(source)
      .then((data) => setPatterns(data.patterns))
      .catch(() => setPatterns([]));
  }, [source.task_key, source.private_task_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const suggest = async () => {
    if (!latestSubmissionId) return;
    setBusy(true);
    setError(null);
    try {
      const { suggestions: found } = await patternsApi.suggest(latestSubmissionId);
      setSuggestions(found);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Wystąpił błąd.");
    } finally {
      setBusy(false);
    }
  };

  const use = (suggestion: PatternSuggestion) => {
    const draft = JSON.stringify({
      trigger: suggestion.trigger,
      action: suggestion.action,
      example: suggestion.example,
    });
    router.push(`/wzorce/nowy?${sourceQuery(source)}&draft=${encodeURIComponent(draft)}`);
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }} component="section" aria-label="Wzorce z tego zadania">
      <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
        Wzorce
      </Typography>

      {patterns.length > 0 && (
        <Box sx={{ mb: 2 }} data-testid="task-patterns">
          <Typography variant="subtitle2" sx={{ color: "grey.600" }}>
            Twoje wzorce z tego zadania
          </Typography>
          <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
            {patterns.map((p) => (
              <li key={p.id}>
                <Link href={`/wzorce/${p.id}`}>
                  <Box component="span" sx={{ "& .math-content": { display: "inline" } }}>
                    <MathContent content={p.trigger} />
                  </Box>
                </Link>
              </li>
            ))}
          </Box>
        </Box>
      )}

      <Typography variant="body2" sx={{ color: "grey.700", mb: 2 }}>
        Zauważyłeś pomysł, który przyda się w innych zadaniach? Zapisz go jako wzorzec i powtarzaj.
      </Typography>

      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: suggestions ? 2 : 0 }}>
        <Button variant="contained" href={`/wzorce/nowy?${sourceQuery(source)}`}>
          Zapisz wzorzec
        </Button>
        {latestSubmissionId && (
          <Button variant="outlined" onClick={suggest} disabled={busy}
            startIcon={busy ? <CircularProgress size={16} /> : null}>
            Podpowiedz wzorzec
          </Button>
        )}
      </Box>

      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

      {suggestions && (
        <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" } }}>
          {suggestions.map((s, i) => (
            <VariantCard key={i} variant={s} label={`Propozycja ${i + 1}`} note={s.why}
              actionLabel="Użyj" onChoose={() => use(s)} />
          ))}
        </Box>
      )}
    </Paper>
  );
}
