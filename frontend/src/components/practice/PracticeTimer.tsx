"use client";

import { Box, Button, Typography, Paper } from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import PauseIcon from "@mui/icons-material/Pause";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import TimerIcon from "@mui/icons-material/Timer";
import { useTimer } from "@/lib/contexts/TimerContext";
import { formatTime } from "@/lib/utils/formatTime";
import { ETAP2_TIMER_DURATION_MS } from "@/lib/utils/constants";

export function PracticeTimer() {
  const { isRunning, isPaused, remainingMs, isHydrated, startTimer, pauseTimer, resumeTimer, resetTimer } = useTimer();

  const isActive = isRunning || isPaused;

  // Show loading state until hydrated
  if (!isHydrated) {
    return (
      <Paper
        sx={{
          p: 2,
          mb: 3,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: "grey.50",
          border: 1,
          borderColor: "grey.200",
          minHeight: 72,
        }}
      >
        <Typography variant="body2" sx={{ color: "grey.500" }}>
          Ładowanie timera...
        </Typography>
      </Paper>
    );
  }

  return (
    <Paper
      sx={{
        p: 2,
        mb: 3,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        bgcolor: isRunning
          ? "rgba(25, 118, 210, 0.08)"
          : isPaused
            ? "rgba(237, 108, 2, 0.08)"
            : "grey.50",
        border: 1,
        borderColor: isRunning ? "primary.light" : isPaused ? "warning.light" : "grey.200",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
        <TimerIcon sx={{ color: isActive ? (isRunning ? "primary.main" : "warning.main") : "grey.500" }} />
        <Box>
          <Typography variant="body2" sx={{ color: "grey.600" }}>
            Czas na rozwiązanie (3 godziny){isPaused && " — PAUZA"}
          </Typography>
          <Typography
            variant="h5"
            sx={{
              fontFamily: "monospace",
              fontWeight: 600,
              color: isRunning
                ? remainingMs < 600000 // Less than 10 minutes
                  ? "error.main"
                  : "primary.main"
                : isPaused
                  ? "warning.main"
                  : "grey.700",
            }}
          >
            {formatTime(remainingMs)}
          </Typography>
        </Box>
      </Box>

      <Box sx={{ display: "flex", gap: 1 }}>
        {isRunning ? (
          <Button
            variant="outlined"
            color="warning"
            startIcon={<PauseIcon />}
            onClick={pauseTimer}
            size="small"
          >
            Pauza
          </Button>
        ) : isPaused ? (
          <Button
            variant="contained"
            startIcon={<PlayArrowIcon />}
            onClick={resumeTimer}
            size="small"
          >
            Wznów
          </Button>
        ) : (
          <Button
            variant="contained"
            startIcon={<PlayArrowIcon />}
            onClick={startTimer}
            size="small"
            disabled={remainingMs === 0}
          >
            Start
          </Button>
        )}
        <Button
          variant="outlined"
          startIcon={<RestartAltIcon />}
          onClick={resetTimer}
          size="small"
          disabled={!isActive && remainingMs === ETAP2_TIMER_DURATION_MS}
        >
          Reset
        </Button>
      </Box>
    </Paper>
  );
}
