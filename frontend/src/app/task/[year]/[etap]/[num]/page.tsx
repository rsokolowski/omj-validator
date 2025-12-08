import { Box, Typography, Paper, Button, Chip, Tooltip } from "@mui/material";
import Link from "next/link";
import { Breadcrumb } from "@/components/layout/Breadcrumb";
import { MathContent } from "@/components/ui/MathContent";
import { DifficultyStars } from "@/components/ui/DifficultyStars";
import { CategoryBadge } from "@/components/ui/CategoryBadge";
import { HintsSection } from "@/components/task/HintsSection";
import { SkillsSection } from "@/components/task/SkillsSection";
import { SubmitSection } from "@/components/task/SubmitSection";
import { SubmissionHistory } from "@/components/task/SubmissionHistory";
import { serverFetch } from "@/lib/api/client";
import { TaskDetailResponse } from "@/lib/types";
import { ETAP_NAMES } from "@/lib/utils/constants";

export const dynamic = "force-dynamic";

interface TaskPageProps {
  params: Promise<{ year: string; etap: string; num: string }>;
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
    <Box sx={{ maxWidth: 900, mx: "auto" }}>
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
            {prerequisite_statuses.map((prereq) => (
              <Tooltip
                key={prereq.key}
                title={<MathContent content={prereq.title} />}
                arrow
              >
                <Link
                  href={prereq.url}
                  style={{ textDecoration: "none" }}
                >
                  <Chip
                    icon={<span>{prereq.status === "mastered" ? "✓" : "○"}</span>}
                    label={`Zad. ${prereq.number} (${prereq.year})`}
                    size="small"
                    sx={{
                      bgcolor: prereq.status === "mastered" ? "#dcfce7" : "#fef3c7",
                      color: prereq.status === "mastered" ? "#166534" : "#92400e",
                      border: `1px solid ${prereq.status === "mastered" ? "#86efac" : "#fcd34d"}`,
                      "&:hover": {
                        bgcolor: prereq.status === "mastered" ? "#bbf7d0" : "#fde68a",
                      },
                    }}
                  />
                </Link>
              </Tooltip>
            ))}
          </Box>
        )}
      </Box>

      {/* Task Content */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}>
          Treść zadania
        </Typography>
        <MathContent content={task.content} className="text-gray-800" />

        {/* PDF Links */}
        {(pdf_links.tasks || pdf_links.solutions) && (
          <Box sx={{ mt: 3, pt: 2, borderTop: 1, borderColor: "grey.200", display: "flex", gap: 1.5, flexWrap: "wrap" }}>
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
        )}
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
