"use client";

import { RefObject } from "react";
import { Box, Paper, Typography, CircularProgress, Button } from "@mui/material";
import AssignmentIcon from "@mui/icons-material/Assignment";
import Link from "next/link";
import { UserSubmissionListItem } from "@/lib/types";
import { SubmissionCard } from "./SubmissionCard";

interface SubmissionsListProps {
  submissions: UserSubmissionListItem[];
  isLoading: boolean;
  sentinelRef: RefObject<HTMLDivElement | null>;
}

export function SubmissionsList({
  submissions,
  isLoading,
  sentinelRef,
}: SubmissionsListProps) {
  // Empty state
  if (submissions.length === 0 && !isLoading) {
    return (
      <Paper
        sx={{
          p: 6,
          textAlign: "center",
          borderRadius: 2,
          border: "1px solid",
          borderColor: "grey.100",
        }}
      >
        <Box
          sx={{
            width: 80,
            height: 80,
            borderRadius: "50%",
            bgcolor: "grey.100",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            mx: "auto",
            mb: 2,
          }}
        >
          <AssignmentIcon sx={{ fontSize: 40, color: "grey.400" }} />
        </Box>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          Brak rozwiazan
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Nie masz jeszcze zadnych rozwiazan. Zacznij od wybrania zadania!
        </Typography>
        <Button
          component={Link}
          href="/years"
          variant="contained"
          sx={{
            bgcolor: "primary.main",
            "&:hover": { bgcolor: "primary.dark" },
          }}
        >
          Przegladaj zadania
        </Button>
      </Paper>
    );
  }

  // Loading state (initial load)
  if (isLoading && submissions.length === 0) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress size={40} />
      </Box>
    );
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {submissions.map((submission) => (
        <SubmissionCard key={submission.id} submission={submission} />
      ))}

      {/* Infinite scroll sentinel */}
      <div ref={sentinelRef} style={{ height: 1 }} />
    </Box>
  );
}
