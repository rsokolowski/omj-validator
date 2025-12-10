"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Box,
  Typography,
  Paper,
  Button,
  FormControlLabel,
  Checkbox,
  Link as MuiLink,
} from "@mui/material";

interface LoginFormProps {
  googleLoginUrl: string;
}

export function LoginForm({ googleLoginUrl }: LoginFormProps) {
  const [accepted, setAccepted] = useState(false);

  return (
    <Paper
      sx={{
        p: 4,
        maxWidth: 400,
        width: "100%",
        textAlign: "center",
      }}
    >
      <Typography
        variant="h4"
        component="h1"
        sx={{ fontWeight: 700, color: "grey.900", mb: 1 }}
      >
        Zaloguj się
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Aby przesyłać rozwiązania i śledzić postępy
      </Typography>

      {/* Regulamin acceptance */}
      <Box
        sx={{
          bgcolor: "grey.50",
          borderRadius: 2,
          p: 2,
          mb: 3,
          textAlign: "left",
        }}
      >
        <FormControlLabel
          control={
            <Checkbox
              checked={accepted}
              onChange={(e) => setAccepted(e.target.checked)}
              sx={{ mt: -1, alignSelf: "flex-start" }}
            />
          }
          label={
            <Typography variant="body2" sx={{ color: "grey.700" }}>
              Akceptuję{" "}
              <Link href="/regulamin" target="_blank" style={{ textDecoration: "none" }}>
                <MuiLink component="span" sx={{ color: "primary.main" }}>
                  regulamin serwisu
                </MuiLink>
              </Link>{" "}
              i zgadzam się na przetwarzanie moich danych zgodnie z polityką
              prywatności.
            </Typography>
          }
          sx={{ alignItems: "flex-start", m: 0 }}
        />
      </Box>

      <Button
        variant="contained"
        size="large"
        fullWidth
        href={googleLoginUrl}
        disabled={!accepted}
        sx={{
          py: 1.5,
          bgcolor: "#4285f4",
          "&:hover": {
            bgcolor: "#3367d6",
          },
          "&.Mui-disabled": {
            bgcolor: "grey.300",
            color: "grey.500",
          },
        }}
      >
        <Box
          component="span"
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1.5,
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              fill="#fff"
            />
            <path
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              fill="#fff"
            />
            <path
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              fill="#fff"
            />
            <path
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              fill="#fff"
            />
          </svg>
          Zaloguj przez Google
        </Box>
      </Button>

      {!accepted && (
        <Typography
          variant="caption"
          sx={{ display: "block", mt: 2, color: "grey.500" }}
        >
          Zaznacz powyższą zgodę, aby kontynuować
        </Typography>
      )}

      <Typography
        variant="caption"
        sx={{ display: "block", mt: 3, color: "grey.500" }}
      >
        Korzystamy z logowania przez Google dla bezpieczeństwa Twojego konta.
      </Typography>
    </Paper>
  );
}
