"use client";

import { Box, Paper, Typography, IconButton, Tooltip } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import PauseIcon from "@mui/icons-material/Pause";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import TimerIcon from "@mui/icons-material/Timer";
import { useTimer } from "@/lib/contexts/TimerContext";
import { formatTime } from "@/lib/utils/formatTime";

export function FloatingTimer() {
  const { isRunning, isPaused, remainingMs, isHydrated, pauseTimer, resumeTimer, resetTimer } = useTimer();

  // Don't show until hydrated (prevents hydration mismatch)
  // Don't show if timer is not active (running or paused)
  if (!isHydrated || (!isRunning && !isPaused)) return null;

  const isLowTime = remainingMs < 600000; // Less than 10 minutes

  const getBgColor = () => {
    if (isPaused) return "rgba(237, 108, 2, 0.08)";
    if (isLowTime) return "rgba(211, 47, 47, 0.08)";
    return "rgba(25, 118, 210, 0.08)";
  };

  const getBorderColor = () => {
    if (isPaused) return "warning.main";
    if (isLowTime) return "error.main";
    return "primary.main";
  };

  const getIconColor = () => {
    if (isPaused) return "warning.main";
    if (isLowTime) return "error.main";
    return "primary.main";
  };

  return (
    <Paper
      elevation={6}
      sx={{
        position: "fixed",
        bottom: 24,
        right: 24,
        zIndex: 1200,
        display: "flex",
        alignItems: "center",
        gap: 1.5,
        py: 1,
        px: 2,
        bgcolor: getBgColor(),
        border: 2,
        borderColor: getBorderColor(),
        borderRadius: 2,
      }}
    >
      <TimerIcon
        sx={{
          color: getIconColor(),
          animation: isLowTime && isRunning ? "pulse 1s infinite" : "none",
          "@keyframes pulse": {
            "0%, 100%": { opacity: 1 },
            "50%": { opacity: 0.5 },
          },
        }}
      />
      <Box>
        <Typography
          variant="caption"
          sx={{ color: "grey.600", display: "block", lineHeight: 1 }}
        >
          Próbny Etap 2{isPaused && " — PAUZA"}
        </Typography>
        {/* Odliczanie nie jest naglowkiem sekcji (WCAG 1.3.1) */}
        <Typography
          variant="h6"
          component="p"
          sx={{
            fontFamily: "monospace",
            fontWeight: 700,
            color: getIconColor(),
            lineHeight: 1.2,
          }}
        >
          {formatTime(remainingMs)}
        </Typography>
      </Box>
      <Box sx={{ display: "flex", gap: 0.5 }}>
        {isRunning ? (
          <Tooltip title="Pauza">
            <IconButton
              size="small"
              onClick={pauseTimer}
              sx={{ color: "grey.500", "&:hover": { color: "warning.main" } }}
            >
              <PauseIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        ) : (
          <Tooltip title="Wznów">
            <IconButton
              size="small"
              onClick={resumeTimer}
              sx={{ color: "warning.main", "&:hover": { color: "success.main" } }}
            >
              <PlayArrowIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
        <Tooltip title="Resetuj timer">
          <IconButton
            size="small"
            onClick={resetTimer}
            sx={{ color: "grey.500", "&:hover": { color: "error.main" } }}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        </Tooltip>
      </Box>
    </Paper>
  );
}
