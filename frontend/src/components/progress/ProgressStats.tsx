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
    // Kolory z motywu - kazdy spelnia 4,5:1 na bialym tle karty (WCAG 1.4.3).
    { label: "Wszystkie zadania", value: stats.total, color: "grey.700" },
    { label: "Opanowane", value: stats.mastered, color: "success.main" },
    { label: "Do rozwiązania", value: stats.unlocked, color: "primary.main" },
    { label: "Sugerowane później", value: stats.locked, color: "grey.500" },
  ];

  const progressPercent = stats.total > 0 ? Math.round((stats.mastered / stats.total) * 100) : 0;

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Grid container spacing={3}>
        {items.map((item) => (
          <Grid key={item.label} size={{ xs: 6, sm: 3 }}>
            <Box sx={{ textAlign: "center" }}>
              {/* Sama liczba nie jest naglowkiem - zachowujemy rozmiar
                  (variant), ale renderujemy akapit (WCAG 1.3.1). */}
              <Typography
                variant="h3"
                component="p"
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
          role="progressbar"
          aria-valuenow={progressPercent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Opanowane zadania: ${stats.mastered} z ${stats.total}`}
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
              // 4,05:1 wobec grey.200 - pasek niesie informacje (WCAG 1.4.11).
              bgcolor: "success.main",
              borderRadius: 1,
              transition: "width 0.3s ease",
            }}
          />
        </Box>
      </Box>
    </Paper>
  );
}
