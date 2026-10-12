"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { Alert, Box, Link as MuiLink, TextField, Typography } from "@mui/material";
import { APIError } from "@/lib/api/client";
import { accountApi, errorText } from "@/lib/api/account";
import { FormCard } from "@/components/account/FormCard";
import { StepHeading } from "@/components/account/StepHeading";
import { SubmitButton } from "@/components/account/SubmitButton";

/** "Nie pamietam hasla": link do zmiany hasla idzie zawsze do rodzica. */
export function PasswordResetRequest() {
  const [login, setLogin] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending) return;
    if (!login.trim()) {
      setFieldError("Wpisz swój login.");
      return;
    }
    setSending(true);
    setError(null);
    try {
      await accountApi.passwordResetRequest(login.trim());
      setSent(true);
    } catch (err) {
      if (err instanceof APIError && err.field === "login") setFieldError(err.message);
      else setError(errorText(err));
    } finally {
      setSending(false);
    }
  };

  return (
    <FormCard>
      <StepHeading focus={sent}>{sent ? "Sprawdźcie skrzynkę rodzica" : "Nie pamiętasz hasła?"}</StepHeading>

      {sent ? (
        <>
          <Alert severity="success" sx={{ mb: 2 }}>
            Jeśli takie konto istnieje, wysłaliśmy rodzicowi link do zmiany hasła.
          </Alert>
          <Typography sx={{ color: "grey.700", mb: 3 }}>
            Link działa przez godzinę. Poproś rodzica, żeby otworzył wiadomość i ustawił nowe
            hasło. Zajrzyjcie też do folderu Spam.
          </Typography>
        </>
      ) : (
        <Box component="form" noValidate onSubmit={submit}>
          <Typography sx={{ color: "grey.700", mb: 3 }}>
            Wpisz swój login. Link do ustawienia nowego hasła wyślemy na adres e-mail rodzica,
            który podano przy zakładaniu konta.
          </Typography>
          <TextField
            id="reset-login"
            label="Login"
            value={login}
            onChange={(e) => {
              setLogin(e.target.value);
              setFieldError(null);
            }}
            error={Boolean(fieldError)}
            helperText={fieldError || " "}
            autoComplete="username"
            disabled={sending}
            fullWidth
            slotProps={{ htmlInput: { autoCapitalize: "none", autoCorrect: "off", spellCheck: false } }}
          />
          <Box aria-live="assertive">
            {error && (
              <Alert severity="error" sx={{ mt: 1 }}>
                {error}
              </Alert>
            )}
          </Box>
          <Box sx={{ mt: 2 }}>
            <SubmitButton busy={sending} busyLabel="Wysyłanie…">
              Wyślij link do rodzica
            </SubmitButton>
          </Box>
          <Typography variant="body2" sx={{ color: "grey.600", mt: 3 }}>
            Logujesz się przez Google? Wtedy nie potrzebujesz hasła z naszej strony — wróć do
            logowania i wybierz „Zaloguj przez Google”.
          </Typography>
        </Box>
      )}

      <Typography variant="body2" sx={{ mt: 3, pt: 2, borderTop: 1, borderColor: "grey.200" }}>
        <MuiLink component={Link} href="/login" sx={{ color: "primary.main" }}>
          Wróć do logowania
        </MuiLink>
      </Typography>
    </FormCard>
  );
}
