"use client";

import Link from "next/link";
import {
  Box,
  Paper,
  Typography,
  Chip,
  LinearProgress,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { GraphNode } from "@/lib/types";
import { MockEtap2Set, getMaxScore, getMasteryThreshold } from "@/lib/utils/constants";
import { DifficultyStars } from "@/components/ui/DifficultyStars";
import { MathContent } from "@/components/ui/MathContent";

interface MockEtap2SetCardProps {
  set: MockEtap2Set;
  nodeMap: Map<string, GraphNode>;
}

export function MockEtap2SetCard({ set, nodeMap }: MockEtap2SetCardProps) {
  // Get tasks for this set
  const tasks = set.tasks
    .map((key) => nodeMap.get(key))
    .filter((n): n is GraphNode => n !== undefined);

  // Calculate total score
  const totalScore = tasks.reduce((sum, task) => sum + task.best_score, 0);
  const maxScore = tasks.length * 6; // 6 points per task

  // Calculate progress percentage
  const progressPercent = maxScore > 0 ? (totalScore / maxScore) * 100 : 0;

  // Check if task is mastered (score >= 5)
  const isTaskMastered = (task: GraphNode): boolean => {
    const threshold = getMasteryThreshold(task.etap);
    return task.best_score >= threshold;
  };

  const masteredCount = tasks.filter(isTaskMastered).length;

  return (
    <Paper sx={{ p: 3 }}>
      {/* Header */}
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 2,
          pb: 1.5,
          borderBottom: 1,
          borderColor: "grey.200",
        }}
      >
        <Typography variant="h6" sx={{ color: "grey.800", fontWeight: 600 }}>
          {set.name}
        </Typography>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <Chip
            label={`${masteredCount}/5 zaliczone`}
            color={masteredCount === 5 ? "success" : "default"}
            size="small"
          />
          <Chip
            label={`${totalScore}/${maxScore} pkt`}
            color={totalScore === maxScore ? "success" : "primary"}
            variant={totalScore > 0 ? "filled" : "outlined"}
            sx={{ fontWeight: 600, minWidth: 90 }}
          />
        </Box>
      </Box>

      {/* Progress bar */}
      <Box sx={{ mb: 2 }}>
        <LinearProgress
          variant="determinate"
          value={progressPercent}
          sx={{
            height: 8,
            borderRadius: 4,
            bgcolor: "grey.200",
            "& .MuiLinearProgress-bar": {
              borderRadius: 4,
              bgcolor: progressPercent === 100 ? "success.main" : "primary.main",
            },
          }}
        />
      </Box>

      {/* Task list */}
      <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
        {tasks.map((task, index) => {
          const maxTaskScore = getMaxScore(task.etap);
          const mastered = isTaskMastered(task);

          return (
            <Link
              key={task.key}
              href={`/task/${task.year}/${task.etap}/${task.number}`}
              style={{ textDecoration: "none" }}
            >
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 1.5,
                  py: 1,
                  px: 1.5,
                  borderRadius: 1,
                  transition: "all 0.15s ease",
                  bgcolor: mastered ? "grey.100" : "transparent",
                  borderLeft: mastered ? 3 : 0,
                  borderColor: "success.main",
                  "&:hover": {
                    bgcolor: mastered ? "grey.200" : "grey.50",
                  },
                }}
              >
                {/* Task number */}
                <Typography
                  variant="body2"
                  sx={{
                    color: "grey.500",
                    fontWeight: 600,
                    minWidth: 30,
                  }}
                >
                  Z{index + 1}
                </Typography>

                {/* Completion indicator */}
                {mastered && (
                  <CheckCircleIcon
                    sx={{ color: "success.main", fontSize: 18 }}
                  />
                )}

                {/* Task identifier */}
                <Typography
                  variant="body2"
                  sx={{
                    color: "grey.700",
                    fontWeight: 500,
                    minWidth: 80,
                    flexShrink: 0,
                  }}
                >
                  {task.year} E2
                </Typography>

                {/* Difficulty */}
                <Box sx={{ flexShrink: 0 }}>
                  <DifficultyStars difficulty={task.difficulty || 3} size="small" />
                </Box>

                {/* Task title */}
                <Box
                  sx={{
                    flex: 1,
                    minWidth: 0,
                    overflow: "hidden",
                    color: "grey.600",
                    "& p": { margin: 0 },
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    component="div"
                  >
                    <MathContent content={task.title} />
                  </Typography>
                </Box>

                {/* Score */}
                <Chip
                  label={
                    task.best_score > 0
                      ? `${task.best_score}/${maxTaskScore}`
                      : "—"
                  }
                  size="small"
                  sx={{
                    minWidth: 50,
                    bgcolor: mastered
                      ? "success.main"
                      : task.best_score > 0
                        ? "warning.light"
                        : "grey.200",
                    color: mastered
                      ? "white"
                      : task.best_score > 0
                        ? "warning.dark"
                        : "grey.600",
                    fontWeight: 600,
                  }}
                />
              </Box>
            </Link>
          );
        })}
      </Box>
    </Paper>
  );
}
