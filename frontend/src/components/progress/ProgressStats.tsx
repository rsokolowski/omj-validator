import { Box, Paper, Typography, Grid } from "@mui/material";

interface ProgressStatsProps {
  stats: {
    total: number;
    mastered: number;
    unlocked: number;
    locked: number;
  };
}

export function ProgressStats({ stats }: ProgressStatsProps) {
  const items = [
    { label: "Wszystkie zadania", value: stats.total, color: "grey.600" },
    { label: "Opanowane", value: stats.mastered, color: "#22c55e" },
    { label: "Do rozwiązania", value: stats.unlocked, color: "#3b82f6" },
    { label: "Sugerowane później", value: stats.locked, color: "#9ca3af" },
  ];

  const progressPercent = stats.total > 0 ? Math.round((stats.mastered / stats.total) * 100) : 0;

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Grid container spacing={3}>
        {items.map((item) => (
          <Grid key={item.label} size={{ xs: 6, sm: 3 }}>
            <Box sx={{ textAlign: "center" }}>
              <Typography
                variant="h3"
                sx={{ fontWeight: 700, color: item.color, mb: 0.5 }}
              >
                {item.value}
              </Typography>
              <Typography variant="body2" sx={{ color: "grey.600" }}>
                {item.label}
              </Typography>
            </Box>
          </Grid>
        ))}
      </Grid>

      {/* Progress bar */}
      <Box sx={{ mt: 3 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
          <Typography variant="body2" sx={{ color: "grey.600" }}>
            Postęp
          </Typography>
          <Typography variant="body2" sx={{ fontWeight: 600, color: "grey.700" }}>
            {progressPercent}%
          </Typography>
        </Box>
        <Box
          sx={{
            height: 8,
            bgcolor: "grey.200",
            borderRadius: 1,
            overflow: "hidden",
          }}
        >
          <Box
            sx={{
              height: "100%",
              width: `${progressPercent}%`,
              bgcolor: "#22c55e",
              borderRadius: 1,
              transition: "width 0.3s ease",
            }}
          />
        </Box>
      </Box>
    </Paper>
  );
}
