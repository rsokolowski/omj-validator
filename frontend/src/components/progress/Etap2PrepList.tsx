"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Box,
  Paper,
  Typography,
  Chip,
  FormControlLabel,
  Switch,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { GraphNode } from "@/lib/types";
import { DifficultyStars } from "@/components/ui/DifficultyStars";
import { MathContent } from "@/components/ui/MathContent";
import {
  ETAP2_PREP_TASKS,
  getMaxScore,
  getMasteryThreshold,
} from "@/lib/utils/constants";

interface Etap2PrepListProps {
  nodes: GraphNode[];
}

export function Etap2PrepList({ nodes }: Etap2PrepListProps) {
  const [hideCompleted, setHideCompleted] = useState(false);

  // Create a map for quick lookup
  const nodeMap = new Map(nodes.map((n) => [n.key, n]));

  // Get prep tasks that exist in the nodes, sorted by difficulty (ascending)
  const allPrepTasks = ETAP2_PREP_TASKS.map((key) => nodeMap.get(key))
    .filter((n): n is GraphNode => n !== undefined)
    .toSorted((a, b) => (a.difficulty || 3) - (b.difficulty || 3));

  // Check if a task is completed (mastered)
  const isCompleted = (task: GraphNode): boolean => {
    const threshold = getMasteryThreshold(task.etap);
    return task.best_score >= threshold;
  };

  // Filter based on toggle
  const displayedTasks = hideCompleted
    ? allPrepTasks.filter((t) => !isCompleted(t))
    : allPrepTasks;

  const completedCount = allPrepTasks.filter(isCompleted).length;
  const totalCount = allPrepTasks.length;

  if (allPrepTasks.length === 0) {
    return null;
  }

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
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
        <Typography variant="h6" sx={{ color: "grey.700" }}>
          Przygotowanie do 2 etapu
        </Typography>
        <Chip
          label={`${completedCount}/${totalCount}`}
          color={completedCount === totalCount ? "success" : "default"}
          size="small"
        />
      </Box>

      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 2,
        }}
      >
        <Typography variant="body2" sx={{ color: "grey.600" }}>
          {completedCount === totalCount
            ? "Gratulacje! Ukończyłeś wszystkie zadania przygotowawcze."
            : `${totalCount - completedCount} zadań do ukończenia`}
        </Typography>
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={hideCompleted}
              onChange={(e) => setHideCompleted(e.target.checked)}
            />
          }
          label={
            <Typography variant="body2" sx={{ color: "grey.600" }}>
              Ukryj ukończone
            </Typography>
          }
          sx={{ mr: 0 }}
        />
      </Box>

      {displayedTasks.length === 0 ? (
        <Typography variant="body2" sx={{ color: "grey.500", fontStyle: "italic" }}>
          Wszystkie zadania ukończone! Wyłącz filtr, aby je zobaczyć.
        </Typography>
      ) : (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
          {displayedTasks.map((task) => {
            const maxScore = getMaxScore(task.etap);
            const completed = isCompleted(task);

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
                    bgcolor: completed ? "grey.100" : "transparent",
                    borderLeft: completed ? 3 : 0,
                    borderColor: "success.main",
                    "&:hover": {
                      bgcolor: completed ? "grey.200" : "grey.50",
                    },
                  }}
                >
                  {/* Completion indicator */}
                  {completed && (
                    <CheckCircleIcon
                      sx={{ color: "success.main", fontSize: 18 }}
                    />
                  )}

                  {/* Task identifier */}
                  <Typography
                    variant="body2"
                    sx={{
                      color: "grey.700",
                      fontWeight: 600,
                      minWidth: 100,
                      flexShrink: 0,
                    }}
                  >
                    {task.year} • Z{task.number}
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
                        ? `${task.best_score}/${maxScore}`
                        : "—"
                    }
                    size="small"
                    sx={{
                      minWidth: 50,
                      bgcolor: completed
                        ? "success.main"
                        : task.best_score > 0
                          ? "warning.light"
                          : "grey.200",
                      color: completed
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
      )}
    </Paper>
  );
}
