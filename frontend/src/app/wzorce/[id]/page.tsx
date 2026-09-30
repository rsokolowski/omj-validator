import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { Box, Button, Chip, Paper, Typography } from "@mui/material";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { MathContent } from "@/components/ui/MathContent";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { PatternActions } from "@/components/patterns/PatternActions";
import { PatternLinks } from "@/components/patterns/PatternLinks";
import { formatDay } from "@/components/patterns/formatDay";
import { APIError, serverFetch } from "@/lib/api/server";
import { PatternDetail } from "@/lib/types";
import { PATTERN_LEVEL_NAMES, REVIEW_OUTCOMES } from "@/lib/utils/constants";
import { formatDate } from "@/lib/utils/dates";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Wzorzec",
  robots: { index: false, follow: false },
};

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ nowy?: string }>;
}

export default async function PatternPage({ params, searchParams }: PageProps) {
  const { id } = await params;
  const { nowy } = await searchParams;
  let pattern: PatternDetail;
  try {
    ({ pattern } = await serverFetch<{ pattern: PatternDetail }>(`/api/patterns/${encodeURIComponent(id)}`));
  } catch (error) {
    if (error instanceof APIError && error.status === 401) {
      redirect(`/login?next=/wzorce/${encodeURIComponent(id)}`);
    }
    if (error instanceof APIError && (error.status === 404 || error.status === 403)) {
      notFound();
    }
    throw error;
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Breadcrumb items={[{ label: "Wzorce", href: "/wzorce" }, { label: "Wzorzec" }]} />

      <Paper sx={{ p: 3 }}>
        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: 2 }}>
          {pattern.category && <CategoryBadge category={pattern.category} size="small" />}
          <Chip size="small" label={PATTERN_LEVEL_NAMES[pattern.level] ?? `Poziom ${pattern.level}`} data-testid="pattern-level" />
          {pattern.archived ? (
            <Chip size="small" label="Wstrzymany" />
          ) : pattern.is_due ? (
            <Chip size="small" color="warning" label="Do powtórki dziś" />
          ) : (
            <Chip size="small" variant="outlined" label={`Następna powtórka: ${formatDay(pattern.due_on)}`} data-testid="pattern-due" />
          )}
          {pattern.origin === "ai_suggested" && <Chip size="small" variant="outlined" label="Z propozycji AI" />}
        </Box>
        <Typography variant="overline" sx={{ color: "grey.600" }}>Kiedy w treści widzę…</Typography>
        <Box sx={{ fontSize: "1.2rem", fontWeight: 600, mb: 2 }}>
          <MathContent content={pattern.trigger} />
        </Box>
        <Typography variant="overline" sx={{ color: "grey.600" }}>…to warto spróbować…</Typography>
        <Box sx={{ mb: pattern.example ? 2 : 0 }}>
          <MathContent content={pattern.action} />
        </Box>
        {pattern.example && (
          <>
            <Typography variant="overline" sx={{ color: "grey.600" }}>Przykład</Typography>
            <MathContent content={pattern.example} />
          </>
        )}
        {pattern.is_due && (
          <Button href="/wzorce/powtorka" variant="contained" sx={{ mt: 2 }}>Powtórz teraz</Button>
        )}
      </Paper>

      <PatternActions key={`${pattern.trigger}|${pattern.action}|${pattern.archived}`} pattern={pattern} />

      <PatternLinks patternId={pattern.id} initialLinks={pattern.links} autoSuggest={nowy === "1"} />

      <Paper sx={{ p: 3 }} component="section" aria-label="Historia powtórek">
        <Typography variant="h6" component="h2" sx={{ mb: 1 }}>Historia powtórek</Typography>
        {pattern.reviews.length === 0 ? (
          <Typography variant="body2" sx={{ color: "grey.600" }}>
            Pierwsza powtórka: {formatDay(pattern.due_on)}.
          </Typography>
        ) : (
          <Box component="ul" sx={{ m: 0, pl: 2 }} data-testid="review-history">
            {pattern.reviews.map((r) => (
              <li key={r.id}>
                <Typography variant="body2">
                  {formatDate(r.created_at)} · {r.kind === "task" ? "Zadanie" : "Przypomnienie"} ·{" "}
                  {REVIEW_OUTCOMES[r.outcome]} · {PATTERN_LEVEL_NAMES[r.level_after]}
                </Typography>
                {r.recall_text && (
                  <Typography variant="body2" component="div" sx={{ color: "grey.600" }}>
                    <MathContent content={`„${r.recall_text}”`} />
                  </Typography>
                )}
              </li>
            ))}
          </Box>
        )}
      </Paper>
    </Box>
  );
}
