import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { Box, Button, Typography } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { PrintButton } from "@/components/patterns/PrintButton";
import { APIError, serverFetch } from "@/lib/api/server";
import { ExerciseLevel } from "@/lib/types";
import { EXERCISE_LEVEL_LABELS } from "@/lib/utils/constants";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Ćwiczenia do wydruku",
  robots: { index: false, follow: false },
};

interface PrintData {
  pattern: { id: string; trigger: string; action: string };
  exercises: {
    id: string;
    title: string;
    content: string;
    exercise_level: ExerciseLevel | null;
    answer: string | null;
    solution: string | null;
  }[];
}

interface PageProps {
  params: Promise<{ id: string }>;
}

function today(): string {
  return new Date().toLocaleDateString("pl-PL", { timeZone: "Europe/Warsaw" });
}

/** A printable sheet: exercises with room to write, answers and solutions on a new page. */
export default async function ExercisesPrintPage({ params }: PageProps) {
  const { id } = await params;
  let data: PrintData;
  try {
    data = await serverFetch<PrintData>(`/api/patterns/${encodeURIComponent(id)}/exercises/print`);
  } catch (error) {
    if (error instanceof APIError && error.status === 401) {
      redirect(`/login?next=/wzorce/${encodeURIComponent(id)}/cwiczenia/druk`);
    }
    if (error instanceof APIError && (error.status === 404 || error.status === 403)) {
      notFound();
    }
    throw error;
  }
  const { pattern, exercises } = data;

  return (
    <Box sx={{ maxWidth: 760, mx: "auto", "& .math-content": { lineHeight: 1.6 } }}>
      <Box className="no-print" sx={{ display: "flex", gap: 1, mb: 3 }}>
        <PrintButton />
        <Button href={`/wzorce/${pattern.id}`}>Wróć do wzorca</Button>
      </Box>

      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" component="h1" sx={{ fontWeight: 700, "& .math-content": { display: "inline" } }}>
          Ćwiczenia: <MathContent content={pattern.trigger} />
        </Typography>
        <Typography variant="body2" sx={{ color: "grey.600" }}>
          Trener OMJ · {today()}
        </Typography>
      </Box>

      {exercises.length === 0 && <Typography>Ten wzorzec nie ma jeszcze ćwiczeń.</Typography>}

      <Box component="ol" sx={{ m: 0, p: 0, listStyle: "none" }}>
        {exercises.map((exercise, index) => (
          <Box component="li" key={exercise.id} sx={{ mb: 2, breakInside: "avoid" }}>
            <Typography sx={{ fontWeight: 700 }} component="div">
              {index + 1}.{" "}
              {exercise.exercise_level && (
                <Box component="span" sx={{ fontWeight: 400, fontStyle: "italic", color: "grey.700" }}>
                  ({EXERCISE_LEVEL_LABELS[exercise.exercise_level]})
                </Box>
              )}
            </Typography>
            <MathContent content={exercise.content} />
            {/* Room to write the solution */}
            <Box sx={{ height: 140, borderBottom: "1px dashed", borderColor: "grey.300" }} />
          </Box>
        ))}
      </Box>

      {exercises.length > 0 && (
        <Box component="section" aria-label="Odpowiedzi" sx={{ breakBefore: "page", pageBreakBefore: "always", pt: 4 }}>
          <Typography variant="h6" component="h2" sx={{ mb: 1 }}>
            Odpowiedzi
          </Typography>
          <Box component="ol" sx={{ m: 0, p: 0, listStyle: "none" }}>
            {exercises.map((exercise, index) => (
              <Box component="li" key={exercise.id} sx={{ display: "flex", gap: 1, mb: 1.5, breakInside: "avoid" }}>
                <Typography component="span" sx={{ fontWeight: 700, lineHeight: 1.8 }}>
                  {index + 1}.
                </Typography>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <MathContent content={exercise.answer || "—"} />
                  {exercise.solution && (
                    <Box sx={{ color: "grey.700", fontSize: "0.9rem", mt: 0.5 }} data-testid="print-solution">
                      <MathContent content={exercise.solution} />
                    </Box>
                  )}
                </Box>
              </Box>
            ))}
          </Box>
        </Box>
      )}
    </Box>
  );
}
