"use client";

import { FormEvent, useState } from "react";
import { Alert, Box, TextField, Typography } from "@mui/material";
import { APIError } from "@/lib/api/client";
import { errorText, parentApi } from "@/lib/api/account";
import { emailProblem, normalizeEmail } from "@/lib/utils/account";
import { SubmitButton } from "@/components/account/SubmitButton";

/**
 * "Wpisz swoj adres, wyslemy Ci link". Odpowiedz jest zawsze taka sama, zeby
 * strona nie zdradzala, czy dany adres ma konto dziecka.
 */
export function ParentLinkRequest() {
  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending) return;
    const normalized = normalizeEmail(email);
    const problem = emailProblem(normalized);
    if (problem) {
      setFieldError(problem);
      return;
    }
    setSending(true);
    setError(null);
    try {
      await parentApi.requestLink(normalized);
      setSent(true);
    } catch (err) {
      if (err instanceof APIError && err.field === "email") setFieldError(err.message);
      else setError(errorText(err));
    } finally {
      setSending(false);
    }
  };

  if (sent) {
    return (
      <Alert severity="success" role="status">
        Jeśli ten adres jest powiązany z kontem dziecka, wysłaliśmy link. Sprawdź skrzynkę (także
        folder Spam).
      </Alert>
    );
  }

  return (
    <Box component="form" noValidate onSubmit={submit} aria-label="Prośba o link do strony rodzica">
      <Typography sx={{ color: "grey.700", mb: 2.5 }}>
        Wpisz swój adres e-mail — ten, który dziecko podało przy zakładaniu konta. Wyślemy Ci link
        do tej strony.
      </Typography>
      <TextField
        id="parent-link-email"
        label="Twój adres e-mail"
        type="email"
        value={email}
        onChange={(e) => {
          setEmail(e.target.value);
          setFieldError(null);
        }}
        error={Boolean(fieldError)}
        helperText={fieldError || " "}
        autoComplete="email"
        disabled={sending}
        fullWidth
        slotProps={{ htmlInput: { inputMode: "email", autoCapitalize: "none", spellCheck: false } }}
      />
      {error && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {error}
        </Alert>
      )}
      <Box sx={{ mt: 2 }}>
        <SubmitButton busy={sending} busyLabel="Wysyłanie…">
          Wyślij link
        </SubmitButton>
      </Box>
    </Box>
  );
}
