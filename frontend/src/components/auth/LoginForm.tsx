"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import {
  Alert,
  Box,
  Checkbox,
  Divider,
  FormControlLabel,
  Link as MuiLink,
  TextField,
  Typography,
} from "@mui/material";
import { accountApi, errorText } from "@/lib/api/account";
import { FormCard } from "@/components/account/FormCard";
import { GoogleButton } from "@/components/account/GoogleButton";
import { PasswordField } from "@/components/account/PasswordField";
import { SubmitButton } from "@/components/account/SubmitButton";

interface LoginFormProps {
  googleLoginUrl: string;
  /** Strona, na ktora wrocic po zalogowaniu (?next=) */
  next?: string;
  /** Komunikat z ?error= (powrot z Google) */
  errorMessage?: string | null;
}

export function LoginForm({ googleLoginUrl, next, errorMessage }: LoginFormProps) {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    if (!login.trim() || !password) {
      setError("Wpisz login i hasło.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await accountApi.login({ login: login.trim(), password, remember, next });
      // Pelne przeladowanie: nowa sesja, swiezy stan klienta
      window.location.href = result.redirect;
    } catch (err) {
      setError(errorText(err));
      setSubmitting(false);
    }
  };

  return (
    <FormCard>
      <Typography
        variant="h4"
        component="h1"
        sx={{ fontWeight: 700, color: "grey.900", mb: 1, fontSize: { xs: "1.75rem", sm: "2.125rem" } }}
      >
        Zaloguj się
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Aby przesyłać rozwiązania i śledzić postępy
      </Typography>

      {errorMessage && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {errorMessage}
        </Alert>
      )}

      <GoogleButton href={googleLoginUrl} />

      <Divider sx={{ my: 3, color: "grey.600", fontSize: "0.875rem" }}>albo loginem i hasłem</Divider>

      <Box component="form" noValidate onSubmit={handleSubmit} aria-label="Logowanie loginem i hasłem">
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
          <TextField
            id="login"
            label="Login"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            autoComplete="username"
            disabled={submitting}
            fullWidth
            slotProps={{ htmlInput: { autoCapitalize: "none", autoCorrect: "off", spellCheck: false } }}
          />
          <PasswordField
            id="password"
            label="Hasło"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
            disabled={submitting}
          />
        </Box>

        <Box
          sx={{
            display: "flex",
            flexWrap: "wrap",
            alignItems: "center",
            justifyContent: "space-between",
            columnGap: 2,
            mt: 1,
          }}
        >
          <FormControlLabel
            control={
              <Checkbox checked={remember} onChange={(e) => setRemember(e.target.checked)} disabled={submitting} />
            }
            label={<Typography variant="body2">Zapamiętaj mnie na tym urządzeniu</Typography>}
          />
          <MuiLink
            component={Link}
            href="/reset-hasla"
            variant="body2"
            sx={{ color: "primary.main", py: 1.5 }}
          >
            Nie pamiętam hasła
          </MuiLink>
        </Box>

        <Box aria-live="assertive">
          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
        </Box>

        <Box sx={{ mt: 2.5, "& > button": { width: "100%" } }}>
          <SubmitButton busy={submitting} busyLabel="Logowanie…">
            Zaloguj się
          </SubmitButton>
        </Box>
      </Box>

      <Box sx={{ mt: 4, pt: 3, borderTop: 1, borderColor: "grey.200", textAlign: "center" }}>
        <Typography sx={{ color: "grey.700" }}>
          Nie masz konta?{" "}
          <MuiLink component={Link} href="/rejestracja" sx={{ color: "primary.main", fontWeight: 600 }}>
            Załóż je
          </MuiLink>
        </Typography>
      </Box>
    </FormCard>
  );
}
