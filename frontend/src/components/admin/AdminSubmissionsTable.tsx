"use client";

import { useState, useCallback, useEffect } from "react";
import {
  Box,
  Paper,
  Typography,
  Chip,
  Button,
  Collapse,
  Divider,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
  Alert,
  Link as MuiLink,
} from "@mui/material";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import HourglassEmptyIcon from "@mui/icons-material/HourglassEmpty";
import ReportProblemIcon from "@mui/icons-material/ReportProblem";
import BlockIcon from "@mui/icons-material/Block";
import Link from "next/link";
import { fetchAPI } from "@/lib/api/client";
import { AdminSubmission, AdminSubmissionsResponse, AdminUser, IssueType } from "@/lib/types";
import { getMaxScore } from "@/lib/utils/constants";
import { useInfiniteScroll } from "@/lib/hooks/useInfiniteScroll";
import { UserAutocomplete } from "./UserAutocomplete";

const PAGE_SIZE = 20;

export function AdminSubmissionsTable() {
  const [submissions, setSubmissions] = useState<AdminSubmission[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Filters
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [issueTypeFilter, setIssueTypeFilter] = useState<IssueType | "">("");

  const fetchSubmissions = useCallback(
    async (newOffset: number, append: boolean = false) => {
      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams({
          offset: newOffset.toString(),
          limit: PAGE_SIZE.toString(),
        });

        if (selectedUser) {
          params.set("user_id", selectedUser.google_sub);
        }
        if (statusFilter) {
          params.set("status", statusFilter);
        }
        if (issueTypeFilter) {
          params.set("issue_type", issueTypeFilter);
        }

        const response = await fetchAPI<AdminSubmissionsResponse>(
          `/api/admin/submissions?${params.toString()}`
        );

        if (append) {
          setSubmissions((prev) => [...prev, ...response.submissions]);
        } else {
          setSubmissions(response.submissions);
        }
        setTotalCount(response.total_count);
        setHasMore(response.has_more);
        setOffset(newOffset);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load submissions");
      } finally {
        setIsLoading(false);
      }
    },
    [selectedUser, statusFilter, issueTypeFilter]
  );

  // Load initial data and when filters change
  useEffect(() => {
    setSubmissions([]);
    setOffset(0);
    setHasMore(true);
    fetchSubmissions(0, false);
  }, [selectedUser, statusFilter, issueTypeFilter, fetchSubmissions]);

  // Handle load more for infinite scroll
  const handleLoadMore = useCallback(() => {
    if (!isLoading && hasMore) {
      fetchSubmissions(offset + PAGE_SIZE, true);
    }
  }, [isLoading, hasMore, offset, fetchSubmissions]);

  const sentinelRef = useInfiniteScroll({
    hasMore,
    isLoading,
    onLoadMore: handleLoadMore,
  });

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

  const renderIssueChip = (submission: AdminSubmission) => {
    if (submission.issue_type === "none") return null;

    if (submission.issue_type === "wrong_task") {
      return (
        <Chip
          icon={<ReportProblemIcon sx={{ fontSize: 16 }} />}
          label="Wrong Task"
          size="small"
          sx={{
            bgcolor: "#fef3c7",
            color: "#92400e",
            border: "1px solid #fcd34d",
            fontWeight: 600,
            "& .MuiChip-icon": { color: "#92400e" },
          }}
        />
      );
    }

    if (submission.issue_type === "injection") {
      return (
        <Chip
          icon={<BlockIcon sx={{ fontSize: 16 }} />}
          label="Injection"
          size="small"
          sx={{
            bgcolor: "#fce7f3",
            color: "#9d174d",
            border: "1px solid #f9a8d4",
            fontWeight: 600,
            "& .MuiChip-icon": { color: "#9d174d" },
          }}
        />
      );
    }

    return null;
  };

  const renderStatusChip = (submission: AdminSubmission) => {
    const maxScore = getMaxScore(submission.etap);

    if (submission.status === "failed") {
      return (
        <Chip
          icon={<ErrorOutlineIcon sx={{ fontSize: 16 }} />}
          label="Failure"
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
          label={submission.status === "pending" ? "Pending" : "Processing"}
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

  const renderFeedback = (submission: AdminSubmission) => {
    if (submission.status === "failed") {
      return (
        <Box sx={{ color: "#991b1b", bgcolor: "#fef2f2", p: 2, borderRadius: 1 }}>
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            Error details:
          </Typography>
          <Typography variant="body2">
            {submission.error_message || "Unknown error"}
          </Typography>
        </Box>
      );
    }

    if (submission.status === "pending" || submission.status === "processing") {
      return (
        <Box sx={{ display: "flex", alignItems: "center", gap: 2, color: "#0369a1" }}>
          <CircularProgress size={20} />
          <Typography variant="body2">
            Submission is being processed...
          </Typography>
        </Box>
      );
    }

    return (
      <Typography variant="body2" sx={{ color: "grey.700", whiteSpace: "pre-wrap" }}>
        {submission.feedback || "No feedback available"}
      </Typography>
    );
  };

  return (
    <Box>
      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
          <UserAutocomplete value={selectedUser} onChange={setSelectedUser} />

          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Status</InputLabel>
            <Select
              value={statusFilter}
              label="Status"
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="pending">Pending</MenuItem>
              <MenuItem value="processing">Processing</MenuItem>
              <MenuItem value="completed">Completed</MenuItem>
              <MenuItem value="failed">Failed</MenuItem>
            </Select>
          </FormControl>

          <FormControl size="small" sx={{ minWidth: 150 }}>
            <InputLabel>Issue Type</InputLabel>
            <Select
              value={issueTypeFilter}
              label="Issue Type"
              onChange={(e) => setIssueTypeFilter(e.target.value as IssueType | "")}
            >
              <MenuItem value="">All</MenuItem>
              <MenuItem value="none">None</MenuItem>
              <MenuItem value="wrong_task">Wrong Task</MenuItem>
              <MenuItem value="injection">Injection</MenuItem>
            </Select>
          </FormControl>

          <Typography variant="body2" color="text.secondary">
            {totalCount} submission{totalCount !== 1 ? "s" : ""} found
          </Typography>
        </Stack>
      </Paper>

      {/* Error */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Submissions list */}
      <Paper sx={{ p: 3 }}>
        {submissions.length === 0 && !isLoading ? (
          <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
            No submissions found
          </Typography>
        ) : (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
            {submissions.map((submission) => {
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
                    <Box sx={{ display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap", flex: 1, minWidth: 0 }}>
                      {/* User info */}
                      <Box sx={{ minWidth: 180, maxWidth: 250 }}>
                        <Typography variant="body2" noWrap title={submission.user_email || "Unknown"}>
                          {submission.user_name || submission.user_email || "Unknown user"}
                        </Typography>
                        {submission.user_name && submission.user_email && (
                          <Typography variant="caption" color="text.secondary" noWrap display="block" title={submission.user_email}>
                            {submission.user_email}
                          </Typography>
                        )}
                      </Box>

                      {/* Task link */}
                      <MuiLink
                        component={Link}
                        href={`/task/${submission.year}/${submission.etap}/${submission.task_number}`}
                        onClick={(e) => e.stopPropagation()}
                        sx={{ fontWeight: 500, fontSize: "0.875rem" }}
                      >
                        {submission.year}/{submission.etap}/{submission.task_number}
                      </MuiLink>

                      {/* Timestamp */}
                      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 130 }}>
                        {formatDate(submission.timestamp)}
                      </Typography>

                      {/* Status chip */}
                      {renderStatusChip(submission)}

                      {/* Issue chip */}
                      {renderIssueChip(submission)}
                    </Box>

                    <Button size="small" sx={{ minWidth: 0, ml: 2 }}>
                      {isExpanded ? "Collapse" : "Expand"}
                    </Button>
                  </Box>

                  <Collapse in={isExpanded}>
                    <Box sx={{ p: 2, pt: 1, bgcolor: "grey.50", borderRadius: "0 0 8px 8px", mt: -0.5 }}>
                      <Divider sx={{ mb: 2 }} />
                      <Typography variant="subtitle2" sx={{ color: "grey.600", mb: 1 }}>
                        {submission.status === "failed" ? "Error details:" : "Feedback:"}
                      </Typography>
                      {renderFeedback(submission)}

                      {/* Abuse detection details */}
                      {submission.issue_type !== "none" && (
                        <Box sx={{ mt: 2, p: 1.5, bgcolor: submission.issue_type === "injection" ? "#fdf2f8" : "#fffbeb", borderRadius: 1 }}>
                          <Typography variant="subtitle2" sx={{ color: submission.issue_type === "injection" ? "#9d174d" : "#92400e", mb: 0.5 }}>
                            Issue detected: {submission.issue_type === "wrong_task" ? "Wrong Task" : "Prompt Injection"}
                          </Typography>
                          <Typography variant="body2" sx={{ color: "grey.700" }}>
                            Abuse confidence score: <strong>{Math.max(0, Math.min(100, submission.abuse_score))}%</strong>
                          </Typography>
                        </Box>
                      )}

                      {/* Images */}
                      {submission.images && submission.images.length > 0 && (
                        <Box sx={{ mt: 2 }}>
                          <Typography variant="subtitle2" sx={{ color: "grey.600", mb: 1 }}>
                            Submitted images:
                          </Typography>
                          <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
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
                                  alt={`Solution ${imgIndex + 1}`}
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
        )}

        {/* Loading indicator */}
        {isLoading && (
          <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
            <CircularProgress size={32} />
          </Box>
        )}

        {/* Infinite scroll sentinel */}
        <div ref={sentinelRef} style={{ height: 1 }} />

        {/* End of list message */}
        {!hasMore && submissions.length > 0 && (
          <Typography variant="body2" color="text.secondary" textAlign="center" py={2}>
            End of submissions
          </Typography>
        )}
      </Paper>
    </Box>
  );
}
