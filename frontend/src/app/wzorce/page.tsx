import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { Alert, Box, Button, Paper, Typography } from "@mui/material";
import { PageHeader } from "@/components/layout/PageHeader";
import { PatternCard } from "@/components/patterns/PatternCard";
import { APIError, serverFetch } from "@/lib/api/server";
import { Pattern, PatternQueue } from "@/lib/types";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Wzorce",
  robots: { index: false, follow: false },
};

interface PageProps {
  searchParams: Promise<{ wstrzymane?: string }>;
}

export default async function PatternsPage({ searchParams }: PageProps) {
  const { wstrzymane } = await searchParams;
  const archived = wstrzymane === "1";
  let patterns: Pattern[];
  let queue: PatternQueue;
  try {
    [{ patterns }, queue] = await Promise.all([
      serverFetch<{ patterns: Pattern[] }>(`/api/patterns${archived ? "?archived=true" : ""}`),
      serverFetch<PatternQueue>("/api/patterns/queue?limit=0"),
    ]);
  } catch (error) {
    if (error instanceof APIError && error.status === 401) {
      redirect("/login?next=/wzorce");
    }
    if (error instanceof APIError && error.status === 403) {
      return (
        <Box>
          <PageHeader title="Wzorce" />
          <Alert severity="warning">Nie masz uprawnień do tej funkcji. Skontaktuj się z administratorem.</Alert>
        </Box>
      );
    }
    throw error;
  }

  return (
    <Box>
      <PageHeader
        title="Wzorce"
        subtitle="Pomysły na rozwiązywanie zadań, które zauważyłeś: kiedy w treści widzę X, to warto spróbować Y. Powtarzaj je, żeby przychodziły same."
      />

      {queue.due_total > 0 && (
        <Paper sx={{ p: 2.5, mb: 3, display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap",
          bgcolor: "#fffbeb", border: "1px solid #fcd34d" }} elevation={0}>
          <Typography sx={{ fontWeight: 600 }}>Do powtórki dziś: {queue.due_total}</Typography>
          <Button href="/wzorce/powtorka" variant="contained">Zacznij</Button>
        </Paper>
      )}

      <Box sx={{ mb: 3, display: "flex", gap: 1, flexWrap: "wrap" }}>
        <Button href="/wzorce/nowy" variant="contained">Nowy wzorzec</Button>
        <Button href={archived ? "/wzorce" : "/wzorce?wstrzymane=1"}>
          {archived ? "Pokaż aktywne" : "Pokaż wstrzymane"}
        </Button>
      </Box>

      {patterns.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: "center" }}>
          <Typography sx={{ color: "grey.700", mb: 1 }}>
            {archived ? "Nie masz wstrzymanych wzorców." : "Nie masz jeszcze żadnych wzorców."}
          </Typography>
          {!archived && (
            <Typography variant="body2" sx={{ color: "grey.600" }}>
              Po rozwiązaniu zadania zapisz pomysł, który pomógł - albo poproś AI o podpowiedź, co
              warto z tego zadania zapamiętać.
            </Typography>
          )}
        </Paper>
      ) : (
        <Box component="section" aria-label="Lista wzorców"
          sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr", md: "1fr 1fr 1fr" } }}>
          {patterns.map((p) => (
            <PatternCard key={p.id} pattern={p} />
          ))}
        </Box>
      )}
    </Box>
  );
}
