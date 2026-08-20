import type { Metadata } from "next";
import { Box, Typography, Paper, Button, Chip, Tooltip, Link as MuiLink } from "@mui/material";
import { BugReport } from "@mui/icons-material";
import Link from "next/link";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { MathContent } from "@/components/ui/MathContent";
import { DifficultyStars } from "@/components/ui/DifficultyStars";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { AiGeneratedNotice } from "@/components/ui/AiGeneratedNotice";
import { HintsSection } from "@/components/task/HintsSection";
import { SkillsSection } from "@/components/task/SkillsSection";
import { SubmitSection } from "@/components/task/SubmitSection";
import { SubmissionHistory } from "@/components/task/SubmissionHistory";
import { serverFetch } from "@/lib/api/server";
import { TaskDetailResponse } from "@/lib/types";
import { ETAP_NAMES, CONTACT_EMAIL, CATEGORY_NAMES } from "@/lib/utils/constants";

export const dynamic = "force-dynamic";

interface TaskPageProps {
  params: Promise<{ year: string; etap: string; num: string }>;
}

export async function generateMetadata({ params }: TaskPageProps): Promise<Metadata> {
  const { year, etap, num } = await params;
  const etapName = ETAP_NAMES[etap] || etap;

  try {
    const data = await getTask(year, etap, num);
    const title = data.task.title.replace(/\$[^$]*\$/g, "").trim();
    const categories = data.task.categories
      .map((c) => CATEGORY_NAMES[c] || c)
      .join(", ");
    const description = `Zadanie ${num} – ${etapName} ${year}. ${categories ? categories + ". " : ""}${title.slice(0, 120)}`;

    return {
      title: `Zadanie ${num} – ${etapName} ${year}`,
      description,
      alternates: { canonical: `/task/${year}/${etap}/${num}` },
      openGraph: {
        title: `Zadanie ${num} – ${etapName} ${year} | OMJ`,
        description,
      },
    };
  } catch {
    return {
      title: `Zadanie ${num} – ${etapName} ${year}`,
    };
  }
}

/** Tytuł zadania bez notacji LaTeX - do nazw dostępnych (WCAG 2.4.4). */
function stripLatex(title: string): string {
  return title.replace(/\$[^$]*\$/g, "").replace(/\s+/g, " ").trim();
}

async function getTask(year: string, etap: string, num: string): Promise<TaskDetailResponse> {
  return serverFetch<TaskDetailResponse>(`/api/task/${year}/${etap}/${num}`);
}

export default async function TaskPage({ params }: TaskPageProps) {
  const { year, etap, num } = await params;
  const data = await getTask(year, etap, num);
  const { task, pdf_links, can_submit, skills_required, skills_gained, prerequisite_statuses, submissions, stats } = data;

  const etapName = ETAP_NAMES[etap] || etap;
  const breadcrumbItems = [
    { label: "Lata", href: "/years" },
    { label: year, href: `/years/${year}` },
    { label: etapName, href: `/years/${year}/${etap}` },
    { label: `Zadanie ${num}` },
  ];

  return (
    <Box>
      <Breadcrumb items={breadcrumbItems} />

      {/* Task Header */}
      <Box sx={{ mb: 4 }}>
        {/* Title row with meta on the right */}
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 2, mb: 1 }}>
          <Typography variant="h4" component="h1" sx={{ fontWeight: 700, color: "grey.900" }}>
            Zadanie {task.number}
          </Typography>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, alignItems: "center" }}>
            <Chip label={year} size="small" sx={{ bgcolor: "grey.100" }} />
            <Chip label={etapName} size="small" sx={{ bgcolor: "grey.100" }} />
            {task.difficulty && <DifficultyStars difficulty={task.difficulty} />}
            {task.categories.map((cat) => (
              <CategoryBadge key={cat} category={cat} />
            ))}
          </Box>
        </Box>
        <Box sx={{ color: "grey.600", mb: 2 }}>
          <MathContent content={task.title} />
        </Box>

        {/* Prerequisites */}
        {prerequisite_statuses.length > 0 && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
            <Typography variant="body2" sx={{ fontWeight: 600, color: "grey.600" }}>
              Powiązane zadania:
            </Typography>
            {prerequisite_statuses.map((prereq) => {
              const isMastered = prereq.status === "mastered";
              const hasStatus = prereq.status !== null;
              // Status jest widoczny jako kolor tła i znak ✓/○ - jedno i drugie
              // jest dla czytnika ekranu nieczytelne, więc powtarzamy je
              // słowami w nazwie linku (WCAG 1.4.1, 2.4.4).
              const statusLabel = !hasStatus
                ? ""
                : isMastered
                  ? " — opanowane"
                  : " — do rozwiązania";
              const prereqTitle = stripLatex(prereq.title);
              return (
                <Tooltip
                  key={prereq.key}
                  title={<MathContent content={prereq.title} />}
                  arrow
                >
                  <Link
                    href={prereq.url}
                    style={{ textDecoration: "none" }}
                    aria-label={`Zadanie ${prereq.number} z ${prereq.year}${prereqTitle ? `: ${prereqTitle}` : ""}${statusLabel}`}
                  >
                    <Chip
                      icon={
                        hasStatus ? (
                          <span aria-hidden="true">{isMastered ? "✓" : "○"}</span>
                        ) : undefined
                      }
                      label={`Zad. ${prereq.number} (${prereq.year})`}
                      size="small"
                      sx={{
                        bgcolor: !hasStatus ? "#f3f4f6" : isMastered ? "#dcfce7" : "#fef3c7",
                        color: !hasStatus ? "#4b5563" : isMastered ? "#166534" : "#92400e",
                        border: `1px solid ${!hasStatus ? "#d1d5db" : isMastered ? "#86efac" : "#fcd34d"}`,
                        "&:hover": {
                          bgcolor: !hasStatus ? "#e5e7eb" : isMastered ? "#bbf7d0" : "#fde68a",
                        },
                      }}
                    />
                  </Link>
                </Tooltip>
              );
            })}
          </Box>
        )}

        {/* Jedno oznaczenie AI obejmujące tytuł i wszystkie metadane zadania
            (trudność, kategorie, powiązania, umiejętności z sekcji poniżej) */}
        <AiGeneratedNotice variant="taskMetadata" display="inline" style={{ marginTop: "12px" }} />
      </Box>

      {/* Task Content */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" component="h2" sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}>
          Treść zadania
        </Typography>
        {task.has_content ? (
          <>
            <AiGeneratedNotice variant="taskContent" style={{ marginBottom: "16px" }} />
            <MathContent content={task.content!} className="text-gray-800" />
          </>
        ) : (
          <Typography sx={{ color: "grey.600", fontStyle: "italic" }}>
            Treść tego zadania nie jest częścią tego repozytorium &mdash; to
            materiał Olimpiady Matematycznej Juniorów. Otwórz oficjalny PDF
            poniżej.
          </Typography>
        )}

        {/* PDF Links and Report Error */}
        <Box sx={{ mt: 3, pt: 2, borderTop: 1, borderColor: "grey.200", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 1.5 }}>
          <Box sx={{ display: "flex", gap: 1.5, flexWrap: "wrap" }}>
            {pdf_links.tasks && (
              <Button
                variant="outlined"
                size="small"
                href={pdf_links.tasks}
                target="_blank"
                rel="noopener noreferrer"
              >
                Zadania PDF
              </Button>
            )}
            {pdf_links.solutions && (
              <Button
                variant="outlined"
                size="small"
                href={pdf_links.solutions}
                target="_blank"
                rel="noopener noreferrer"
              >
                Rozwiązania PDF
              </Button>
            )}
          </Box>
          <MuiLink
            href={`mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(`Błąd w zadaniu ${num} (${year} ${etapName})`)}&body=${encodeURIComponent(`Zgłaszam błąd w zadaniu:\n\nZadanie: ${num}\nRok: ${year}\nEtap: ${etapName}\n\nOpis błędu:\n\n`)}`}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 0.5,
              color: "grey.500",
              fontSize: "0.8125rem",
              textDecoration: "none",
              "&:hover": { color: "error.main" },
            }}
          >
            <BugReport sx={{ fontSize: 18 }} />
            Zgłoś błąd
          </MuiLink>
        </Box>
      </Paper>

      {/* Skills Section */}
      {(skills_required.length > 0 || skills_gained.length > 0) && (
        <SkillsSection skillsRequired={skills_required} skillsGained={skills_gained} />
      )}

      {/* Hints Section */}
      {task.hints.length > 0 && (
        <HintsSection hints={task.hints} />
      )}

      {/* Submit Section */}
      <SubmitSection
        year={year}
        etap={etap}
        num={parseInt(num)}
        canSubmit={can_submit}
        isAuthenticated={data.is_authenticated}
      />

      {/* Submission History */}
      {can_submit && submissions.length > 0 && (
        <SubmissionHistory
          submissions={submissions}
          totalCount={stats?.submission_count || submissions.length}
        />
      )}
    </Box>
  );
}
