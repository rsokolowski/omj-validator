"use client";

import { useState } from "react";
import {
  Box,
  Typography,
  Chip,
  Collapse,
  Divider,
  Stack,
  Button,
  Link as MuiLink,
  CircularProgress,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import HourglassEmptyIcon from "@mui/icons-material/HourglassEmpty";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import Link from "next/link";
import { UserSubmissionListItem } from "@/lib/types";
import { ETAP_NAMES, CATEGORY_NAMES } from "@/lib/utils/constants";
import { MathContent } from "@/components/ui/MathContent";

interface SubmissionCardProps {
  submission: UserSubmissionListItem;
}

function getScoreColor(score: number, maxScore: number) {
  const ratio = score / maxScore;
  if (ratio >= 0.8) return { bg: "#dcfce7", color: "#166534", border: "#86efac" };
  if (ratio >= 0.4) return { bg: "#fef3c7", color: "#92400e", border: "#fcd34d" };
  return { bg: "#fee2e2", color: "#991b1b", border: "#fca5a5" };
}

function formatDate(dateString: string) {
  const date = new Date(dateString);
  return new Intl.DateTimeFormat("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function SubmissionCard({ submission }: SubmissionCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const renderStatusChip = () => {
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

    if (submission.status === "pending" || submission.status === "processing") {
      return (
        <Chip
          icon={<HourglassEmptyIcon sx={{ fontSize: 16 }} />}
          label={submission.status === "pending" ? "Oczekuje" : "Przetwarzanie"}
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

    // Completed status
    const score = submission.score ?? 0;
    const scoreColors = getScoreColor(score, submission.max_score);
    return (
      <Chip
        icon={<CheckCircleIcon sx={{ fontSize: 16 }} />}
        label={`${score}/${submission.max_score} pkt`}
        size="small"
        sx={{
          bgcolor: scoreColors.bg,
          color: scoreColors.color,
          border: `1px solid ${scoreColors.border}`,
          fontWeight: 600,
          "& .MuiChip-icon": { color: scoreColors.color },
        }}
      />
    );
  };

  const renderFeedback = () => {
    if (submission.status === "failed") {
      return (
        <Box sx={{ color: "#991b1b", bgcolor: "#fef2f2", p: 2, borderRadius: 1 }}>
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            Szczegóły błędu:
          </Typography>
          <Typography variant="body2">
            {submission.error_message || "Nieznany błąd"}
          </Typography>
        </Box>
      );
    }

    if (submission.status === "pending" || submission.status === "processing") {
      return (
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, color: "#0369a1" }}>
          <CircularProgress size={20} />
          <Typography variant="body2">
            Rozwiązanie jest przetwarzane...
          </Typography>
        </Box>
      );
    }

    return (
      <Typography variant="body2" sx={{ color: "grey.700", whiteSpace: "pre-wrap" }}>
        {submission.feedback || "Brak komentarza"}
      </Typography>
    );
  };

  return (
    <Box
      sx={{
        bgcolor: "white",
        borderRadius: 2,
        border: "1px solid",
        borderColor: "grey.200",
        overflow: "hidden",
        transition: "box-shadow 0.2s",
        "&:hover": {
          boxShadow: 1,
        },
      }}
    >
      {/* Header Row */}
      <Box
        sx={{
          p: 2,
          cursor: "pointer",
          transition: "background-color 0.15s",
          "&:hover": { bgcolor: "grey.50" },
        }}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <Stack
          direction={{ xs: "column", sm: "row" }}
          spacing={{ xs: 1.5, sm: 2 }}
          alignItems={{ xs: "flex-start", sm: "center" }}
          justifyContent="space-between"
        >
          {/* Left side: Task info */}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box sx={{ mb: 0.5 }}>
              <MuiLink
                component={Link}
                href={`/task/${submission.year}/${submission.etap}/${submission.task_number}`}
                onClick={(e) => e.stopPropagation()}
                sx={{
                  fontWeight: 600,
                  fontSize: "0.95rem",
                  color: "primary.main",
                  textDecoration: "none",
                  "&:hover": { textDecoration: "underline" },
                  "& .math-content": { display: "inline" },
                }}
              >
                <MathContent content={submission.task_title} />
              </MuiLink>
            </Box>
            <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
              <Typography variant="caption" color="text.secondary">
                {submission.year} / {ETAP_NAMES[submission.etap] || submission.etap} / Zadanie {submission.task_number}
              </Typography>
              <Typography variant="caption" color="text.disabled">
                {formatDate(submission.timestamp)}
              </Typography>
            </Stack>
          </Box>

          {/* Center: Categories */}
          <Stack
            direction="row"
            spacing={0.5}
            sx={{ display: { xs: "none", md: "flex" } }}
          >
            {submission.task_categories.slice(0, 2).map((cat) => (
              <Chip
                key={cat}
                label={CATEGORY_NAMES[cat] || cat}
                size="small"
                sx={{
                  bgcolor: "grey.100",
                  color: "grey.700",
                  fontSize: "0.7rem",
                  height: 22,
                }}
              />
            ))}
          </Stack>

          {/* Right side: Status + Expand */}
          <Stack direction="row" spacing={1.5} alignItems="center">
            {renderStatusChip()}
            <Button
              size="small"
              sx={{
                minWidth: 0,
                p: 0.5,
                color: "text.secondary",
              }}
            >
              {isExpanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
            </Button>
          </Stack>
        </Stack>
      </Box>

      {/* Expanded Content */}
      <Collapse in={isExpanded}>
        <Divider />
        <Box sx={{ p: 2, bgcolor: "grey.50" }}>
          {/* Feedback */}
          <Typography variant="subtitle2" sx={{ color: "grey.600", mb: 1 }}>
            {submission.status === "failed" ? "Szczegóły błędu:" : "Komentarz:"}
          </Typography>
          {renderFeedback()}

          {/* Images */}
          {submission.images && submission.images.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" sx={{ color: "grey.600", mb: 1 }}>
                Przesłane zdjęcia:
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {submission.images.map((image, imgIndex) => (
                  <a
                    key={imgIndex}
                    href={`/uploads/${image}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Box
                      component="img"
                      src={`/uploads/${image}`}
                      alt={`Zdjęcie ${imgIndex + 1}`}
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
              </Stack>
            </Box>
          )}
        </Box>
      </Collapse>
    </Box>
  );
}
