"use client";

import { useState } from "react";
import { Paper, Typography, Box, Chip, Button, Collapse, Divider, CircularProgress } from "@mui/material";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import HourglassEmptyIcon from "@mui/icons-material/HourglassEmpty";
import { Submission } from "@/lib/types";
import { getMaxScore } from "@/lib/utils/constants";
import { MathContent } from "@/components/ui/MathContent";

interface SubmissionHistoryProps {
  submissions: Submission[];
  totalCount: number;
}

export function SubmissionHistory({ submissions, totalCount }: SubmissionHistoryProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const getScoreColor = (score: number, maxScore: number) => {
    const ratio = score / maxScore;
    if (ratio >= 0.8) return { bg: "#dcfce7", color: "#166534", border: "#86efac" };
    if (ratio >= 0.4) return { bg: "#fef3c7", color: "#92400e", border: "#fcd34d" };
    return { bg: "#fee2e2", color: "#991b1b", border: "#fca5a5" };
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return new Intl.DateTimeFormat("pl-PL", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  };

  const renderStatusChip = (submission: Submission, maxScore: number) => {
    // Failed submission
    if (submission.status === "failed") {
      return (
        <Chip
          icon={<ErrorOutlineIcon sx={{ fontSize: 16 }} />}
          label="Błąd"
          size="small"
          sx={{
            bgcolor: "#fef2f2",
            color: "#991b1b",
            border: "1px solid #fecaca",
            fontWeight: 600,
            "& .MuiChip-icon": { color: "#991b1b" },
          }}
        />
      );
    }

    // Pending or processing
    if (submission.status === "pending" || submission.status === "processing") {
      return (
        <Chip
          icon={<HourglassEmptyIcon sx={{ fontSize: 16 }} />}
          label="W trakcie..."
          size="small"
          sx={{
            bgcolor: "#f0f9ff",
            color: "#0369a1",
            border: "1px solid #bae6fd",
            fontWeight: 600,
            "& .MuiChip-icon": { color: "#0369a1" },
          }}
        />
      );
    }

    // Completed - show score
    const score = submission.score ?? 0;
    const scoreColors = getScoreColor(score, maxScore);
    return (
      <Chip
        label={`${score}/${maxScore}`}
        size="small"
        sx={{
          bgcolor: scoreColors.bg,
          color: scoreColors.color,
          border: `1px solid ${scoreColors.border}`,
          fontWeight: 600,
        }}
      />
    );
  };

  const renderFeedback = (submission: Submission) => {
    if (submission.status === "failed") {
      return (
        <Box sx={{ color: "#991b1b", bgcolor: "#fef2f2", p: 2, borderRadius: 1 }}>
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            Wystąpił błąd podczas przetwarzania:
          </Typography>
          <Typography variant="body2">
            {submission.error_message || "Nieznany błąd. Spróbuj przesłać rozwiązanie ponownie."}
          </Typography>
        </Box>
      );
    }

    if (submission.status === "pending" || submission.status === "processing") {
      return (
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, color: "#0369a1" }}>
          <CircularProgress size={20} />
          <Typography variant="body2">
            Rozwiązanie jest przetwarzane. Odśwież stronę, aby zobaczyć wynik.
          </Typography>
        </Box>
      );
    }

    return (
      <Box sx={{ color: "grey.700", "& p": { margin: 0 } }}>
        <MathContent content={submission.feedback || "Brak feedbacku"} />
      </Box>
    );
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}>
        Historia rozwiązań ({totalCount})
      </Typography>

      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
        {submissions.map((submission, index) => {
          const maxScore = getMaxScore(submission.etap);
          const isExpanded = expandedId === submission.id;

          return (
            <Box key={submission.id}>
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  p: 2,
                  bgcolor: "grey.50",
                  borderRadius: 1,
                  cursor: "pointer",
                  transition: "background-color 0.15s",
                  "&:hover": {
                    bgcolor: "grey.100",
                  },
                }}
                onClick={() => setExpandedId(isExpanded ? null : submission.id)}
              >
                <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                  <Typography variant="body2" sx={{ color: "grey.500", minWidth: 24 }}>
                    #{totalCount - index}
                  </Typography>
                  {renderStatusChip(submission, maxScore)}
                  <Typography variant="body2" sx={{ color: "grey.600" }}>
                    {formatDate(submission.timestamp)}
                  </Typography>
                </Box>
                <Button size="small" sx={{ minWidth: 0 }}>
                  {isExpanded ? "Zwiń" : "Rozwiń"}
                </Button>
              </Box>

              <Collapse in={isExpanded}>
                <Box sx={{ p: 2, pt: 1, bgcolor: "grey.50", borderRadius: "0 0 8px 8px", mt: -0.5 }}>
                  <Divider sx={{ mb: 2 }} />
                  <Typography variant="subtitle2" sx={{ color: "grey.600", mb: 1 }}>
                    {submission.status === "failed" ? "Szczegóły błędu:" : "Ocena:"}
                  </Typography>
                  {renderFeedback(submission)}

                  {submission.images && submission.images.length > 0 && (
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="subtitle2" sx={{ color: "grey.600", mb: 1 }}>
                        Przesłane zdjęcia:
                      </Typography>
                      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                        {submission.images.map((image, imgIndex) => (
                          <a
                            key={imgIndex}
                            href={`/uploads/${image}`}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            <Box
                              component="img"
                              src={`/uploads/${image}`}
                              alt={`Rozwiązanie ${imgIndex + 1}`}
                              sx={{
                                width: 80,
                                height: 80,
                                objectFit: "cover",
                                borderRadius: 1,
                                border: "1px solid",
                                borderColor: "grey.200",
                                transition: "transform 0.15s",
                                "&:hover": {
                                  transform: "scale(1.05)",
                                },
                              }}
                            />
                          </a>
                        ))}
                      </Box>
                    </Box>
                  )}
                </Box>
              </Collapse>
            </Box>
          );
        })}
      </Box>
    </Paper>
  );
}
