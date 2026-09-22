"use client";

import { Box, Button, Typography, Paper } from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import PauseIcon from "@mui/icons-material/Pause";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import TimerIcon from "@mui/icons-material/Timer";
import { useTimer } from "@/lib/contexts/TimerContext";
import { formatTime } from "@/lib/utils/formatTime";
import {
  MockEtap,
  MOCK_ETAP_CONFIG,
  MOCK_ETAP_DURATION_LABELS,
} from "@/lib/utils/constants";

interface PracticeTimerProps {
  etap: MockEtap;
}

export function PracticeTimer({ etap }: PracticeTimerProps) {
  const {
    etap: timerEtap,
    isRunning,
    isPaused,
    remainingMs,
    isHydrated,
    startTimer,
    pauseTimer,
    resumeTimer,
    resetTimer,
  } = useTimer();

  const config = MOCK_ETAP_CONFIG[etap];

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

  // Timer uruchomiony dla drugiego etapu - nie pozwalamy go tu sterowac,
  // pokazujemy tylko czyj to czas i przycisk Reset.
  const otherEtap =
    (isRunning || isPaused) && timerEtap !== null && timerEtap !== etap
      ? timerEtap
      : null;

  if (otherEtap) {
    const otherConfig = MOCK_ETAP_CONFIG[otherEtap];
    return (
      <Paper
        sx={{
          p: 2,
          mb: 3,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 2,
          flexWrap: "wrap",
          bgcolor: "grey.50",
          border: 1,
          borderColor: "grey.300",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <TimerIcon sx={{ color: "grey.500" }} />
          <Box>
            <Typography variant="body2" sx={{ color: "grey.600" }}>
              {otherConfig.label}
              {isPaused && " — PAUZA"}
            </Typography>
            {/* Odliczanie nie jest naglowkiem sekcji (WCAG 1.3.1) */}
            <Typography
              variant="h5"
              component="p"
              sx={{
                fontFamily: "monospace",
                fontWeight: 600,
                color: "grey.700",
              }}
            >
              {formatTime(remainingMs)}
            </Typography>
            <Typography variant="caption" sx={{ color: "grey.600" }}>
              Trwa odliczanie dla innego zestawu. Zresetuj je, aby zacząć{" "}
              {config.label}.
            </Typography>
          </Box>
        </Box>
        <Button
          variant="outlined"
          startIcon={<RestartAltIcon />}
          onClick={resetTimer}
          size="small"
        >
          Reset
        </Button>
      </Paper>
    );
  }

  const isActive = isRunning || isPaused;
  // Gdy timer nie dotyczy tego etapu, pokazujemy pelny czas do rozpoczecia.
  const displayedMs = timerEtap === etap ? remainingMs : config.timerMs;
  const isExpired = timerEtap === etap && !isActive && remainingMs === 0;

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
            Czas na rozwiązanie ({MOCK_ETAP_DURATION_LABELS[etap]})
            {isPaused && " — PAUZA"}
          </Typography>
          {/* Odliczanie nie jest naglowkiem sekcji (WCAG 1.3.1) */}
          <Typography
            variant="h5"
            component="p"
            sx={{
              fontFamily: "monospace",
              fontWeight: 600,
              color: isRunning
                ? displayedMs < 600000 // Less than 10 minutes
                  ? "error.main"
                  : "primary.main"
                : isPaused
                  ? "warning.main"
                  : "grey.700",
            }}
          >
            {formatTime(displayedMs)}
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
            onClick={() => startTimer(etap)}
            size="small"
            disabled={isExpired}
          >
            Start
          </Button>
        )}
        <Button
          variant="outlined"
          startIcon={<RestartAltIcon />}
          onClick={resetTimer}
          size="small"
          disabled={!isActive && timerEtap !== etap}
        >
          Reset
        </Button>
      </Box>
    </Paper>
  );
}
