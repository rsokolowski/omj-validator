import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { Box, Chip, Paper, Typography } from "@mui/material";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { MathContent } from "@/components/ui/MathContent";
import { DifficultyStars } from "@/components/ui/DifficultyStars";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { AiGeneratedNotice } from "@/components/ui/AiGeneratedNotice";
import { SubmitSection } from "@/components/task/SubmitSection";
import { SubmissionHistory } from "@/components/task/SubmissionHistory";
import { PrivateHintsSection } from "@/components/private-tasks/PrivateHintsSection";
import { PrivateTaskActions } from "@/components/private-tasks/PrivateTaskActions";
import { SourcePhotos } from "@/components/private-tasks/SourcePhotos";
import { APIError, serverFetch } from "@/lib/api/server";
import { PrivateTaskDetailResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

// A private task is never indexed and its title stays out of <title>, which
// ends up in browser history and shared-device tab lists
export const metadata: Metadata = {
  title: "Moje zadanie",
  robots: { index: false, follow: false },
};

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ ocena?: string | string[] }>;
}

// Submission ids are the first 8 characters of a uuid4
const SUBMISSION_ID = /^[0-9a-f]{8}$/;

export default async function PrivateTaskPage({ params, searchParams }: PageProps) {
  const { id } = await params;
  // Set by "Odczytaj zadanie i oceń", which sends the solution before coming here
  const { ocena } = await searchParams;
  const resumeSubmissionId = typeof ocena === "string" && SUBMISSION_ID.test(ocena) ? ocena : undefined;
  let data: PrivateTaskDetailResponse;
  try {
    data = await serverFetch<PrivateTaskDetailResponse>(`/api/private-tasks/${encodeURIComponent(id)}`);
  } catch (error) {
    if (error instanceof APIError && error.status === 401) {
      redirect(`/login?next=/moje-zadania/${encodeURIComponent(id)}`);
    }
    if (error instanceof APIError && (error.status === 404 || error.status === 403)) {
      notFound();
    }
    throw error;
  }

  const { task, submissions, stats } = data;

  return (
    <Box>
      <Breadcrumb items={[{ label: "Moje zadania", href: "/moje-zadania" }, { label: "Zadanie" }]} />

      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 2, mb: 1 }}>
          <Typography variant="h4" component="h1" sx={{ fontWeight: 700, color: "grey.900" }}>
            <MathContent content={task.title} />
          </Typography>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
            {task.source_label && <Chip label={task.source_label} size="small" sx={{ bgcolor: "grey.100" }} />}
            {task.difficulty && <DifficultyStars difficulty={task.difficulty} />}
            {task.category && <CategoryBadge category={task.category} />}
          </Box>
        </Box>
        <Chip
          label="Zadanie prywatne · ocena bez oficjalnego rozwiązania"
          size="small"
          sx={{ bgcolor: "#eef2ff", color: "#3730a3", border: "1px solid #c7d2fe", mb: 2 }}
        />
        <PrivateTaskActions task={task} />
      </Box>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" component="h2" sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}>
          Treść zadania
        </Typography>
        {task.origin === "photo" && (
          <AiGeneratedNotice variant="taskContent" style={{ marginBottom: "16px" }} />
        )}
        <MathContent content={task.content} className="text-gray-800" />
        <SourcePhotos photos={task.source_images} />
      </Paper>

      {task.hints_count > 0 && (
        <PrivateHintsSection
          key={`${task.hints_count}-${task.revealed_hints.join("|")}`}
          taskId={task.id}
          hintsCount={task.hints_count}
          initialRevealed={task.revealed_hints}
        />
      )}

      <Paper sx={{ p: 2, mb: 3, bgcolor: "#fffbeb", border: "1px solid #fcd34d" }} elevation={0}>
        <Typography variant="body2" sx={{ color: "#92400e" }}>
          To zadanie nie ma oficjalnego rozwiązania, więc AI najpierw rozwiązuje je samo, a potem
          ocenia Twoją pracę. Ocena może być mniej pewna niż przy zadaniach z archiwum OMJ - jeśli
          wynik Cię dziwi, porównaj go z rozwiązaniem ze źródła zadania.
        </Typography>
      </Paper>

      <SubmitSection
        canSubmit
        isAuthenticated
        submitUrl={`/api/private-tasks/${task.id}/submit`}
        pagePath={`/moje-zadania/${task.id}`}
        resumeSubmissionId={resumeSubmissionId}
      />

      {submissions.length > 0 && (
        <SubmissionHistory submissions={submissions} totalCount={stats.submission_count} />
      )}
    </Box>
  );
}
