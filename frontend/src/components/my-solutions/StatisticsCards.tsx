"use client";

import { Box, Paper, Typography, Grid, LinearProgress } from "@mui/material";
import AssignmentIcon from "@mui/icons-material/Assignment";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import StarIcon from "@mui/icons-material/Star";
import EmojiEventsIcon from "@mui/icons-material/EmojiEvents";
import { UserSubmissionStats } from "@/lib/types";

interface StatisticsCardsProps {
  stats: UserSubmissionStats;
}

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  subtext?: string;
  color: string;
  bgColor: string;
}

function StatCard({ icon, label, value, subtext, color, bgColor }: StatCardProps) {
  return (
    <Paper
      sx={{
        p: 2.5,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        gap: 1,
        borderRadius: 2,
        border: "1px solid",
        borderColor: "grey.100",
        transition: "transform 0.2s, box-shadow 0.2s",
        "&:hover": {
          transform: "translateY(-2px)",
          boxShadow: 2,
        },
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
        <Box
          sx={{
            p: 1,
            borderRadius: 1.5,
            bgcolor: bgColor,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: color,
          }}
        >
          {icon}
        </Box>
        <Typography variant="body2" color="text.secondary" fontWeight={500}>
          {label}
        </Typography>
      </Box>
      <Typography variant="h4" fontWeight={700} color={color}>
        {value}
      </Typography>
      {subtext && (
        <Typography variant="caption" color="text.secondary">
          {subtext}
        </Typography>
      )}
    </Paper>
  );
}

export function StatisticsCards({ stats }: StatisticsCardsProps) {
  const completionRate = stats.total_submissions > 0
    ? Math.round((stats.completed_count / stats.total_submissions) * 100)
    : 0;

  const masteryRate = stats.tasks_attempted > 0
    ? Math.round((stats.tasks_mastered / stats.tasks_attempted) * 100)
    : 0;

  return (
    <Box sx={{ mb: 4 }}>
      <Grid container spacing={2}>
        {/* Total Submissions */}
        <Grid size={{ xs: 6, sm: 6, md: 3 }}>
          <StatCard
            icon={<AssignmentIcon fontSize="small" />}
            label="Wszystkie"
            value={stats.total_submissions}
            subtext={`${stats.pending_count} w trakcie`}
            color="#3b82f6"
            bgColor="#eff6ff"
          />
        </Grid>

        {/* Completed */}
        <Grid size={{ xs: 6, sm: 6, md: 3 }}>
          <StatCard
            icon={<CheckCircleIcon fontSize="small" />}
            label="Ukonczone"
            value={stats.completed_count}
            subtext={`${completionRate}% skutecznosci`}
            color="#22c55e"
            bgColor="#f0fdf4"
          />
        </Grid>

        {/* Average Score */}
        <Grid size={{ xs: 6, sm: 6, md: 3 }}>
          <StatCard
            icon={<StarIcon fontSize="small" />}
            label="Srednia"
            value={stats.avg_score !== null ? stats.avg_score.toFixed(1) : "-"}
            subtext={stats.best_score !== null ? `Najlepszy: ${stats.best_score} pkt` : undefined}
            color="#f59e0b"
            bgColor="#fffbeb"
          />
        </Grid>

        {/* Tasks Mastered */}
        <Grid size={{ xs: 6, sm: 6, md: 3 }}>
          <StatCard
            icon={<EmojiEventsIcon fontSize="small" />}
            label="Opanowane"
            value={stats.tasks_mastered}
            subtext={`z ${stats.tasks_attempted} probowanych zadan`}
            color="#8b5cf6"
            bgColor="#f5f3ff"
          />
        </Grid>
      </Grid>

      {/* Progress Bar */}
      {stats.tasks_attempted > 0 && (
        <Paper
          sx={{
            mt: 2,
            p: 2,
            borderRadius: 2,
            border: "1px solid",
            borderColor: "grey.100",
          }}
        >
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="body2" fontWeight={500}>
              Postep w nauce
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {stats.tasks_mastered} z {stats.tasks_attempted} zadan opanowanych
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={masteryRate}
            sx={{
              height: 8,
              borderRadius: 4,
              bgcolor: "#f3f4f6",
              "& .MuiLinearProgress-bar": {
                borderRadius: 4,
                background: "linear-gradient(90deg, #8b5cf6 0%, #a78bfa 100%)",
              },
            }}
          />
        </Paper>
      )}
    </Box>
  );
}
