"use client";

import { useState } from "react";
import { Paper, Typography, Box, Chip, Button, Collapse, Divider } from "@mui/material";
import { Submission } from "@/lib/types";
import { getMaxScore } from "@/lib/utils/constants";

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

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}>
        Historia rozwiązań ({totalCount})
      </Typography>

      <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
        {submissions.map((submission, index) => {
          const maxScore = getMaxScore(submission.etap);
          const score = submission.score ?? 0;
          const scoreColors = getScoreColor(score, maxScore);
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
                    Ocena:
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ color: "grey.700", whiteSpace: "pre-wrap" }}
                  >
                    {submission.feedback || "Brak feedbacku"}
                  </Typography>

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
