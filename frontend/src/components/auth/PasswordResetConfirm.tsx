"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Alert, Box, Button, CircularProgress, Typography } from "@mui/material";
import CheckCircleOutline from "@mui/icons-material/CheckCircleOutline";
import { APIError } from "@/lib/api/client";
import { accountApi, errorText } from "@/lib/api/account";
import type { LinkState } from "@/lib/types";
import { passwordProblem } from "@/lib/utils/account";
import { FormCard } from "@/components/account/FormCard";
import { StepHeading } from "@/components/account/StepHeading";
import { PasswordField } from "@/components/account/PasswordField";
import { SubmitButton } from "@/components/account/SubmitButton";

type View =
  | { kind: "loading" }
  | { kind: "load_error"; message: string }
  | { kind: "form"; login: string }
  | { kind: "problem"; state: Exclude<LinkState, "valid"> }
  | { kind: "done" };

/** Strona z linku "Zmiana hasla" (otwiera ja zwykle rodzic). Nikogo nie loguje. */
export function PasswordResetConfirm({ token }: { token: string | null }) {
  const [view, setView] = useState<View>(token ? { kind: "loading" } : { kind: "problem", state: "invalid" });
  const [acted, setActed] = useState(false);
  const [password, setPassword] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const check = useCallback(async () => {
    if (!token) return;
    try {
      const result = await accountApi.passwordResetCheck(token);
      setView(
        result.state === "valid" && result.login
          ? { kind: "form", login: result.login }
          : { kind: "problem", state: result.state === "valid" ? "invalid" : result.state }
      );
    } catch (err) {
      setView({ kind: "load_error", message: errorText(err) });
    }
  }, [token]);

  useEffect(() => {
    void check();
  }, [check]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!token || saving || view.kind !== "form") return;
    const problem = passwordProblem(password, view.login);
    if (problem) {
      setFieldError(problem);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await accountApi.passwordResetConfirm(token, password);
      setActed(true);
      setView({ kind: "done" });
    } catch (err) {
      if (err instanceof APIError && err.status === 410) {
        setActed(true);
        const state = err.state;
        setView({ kind: "problem", state: state === "expired" || state === "used" ? state : "invalid" });
      } else if (err instanceof APIError && err.field === "password") {
        setFieldError(err.message);
      } else {
        setError(errorText(err));
      }
    } finally {
      setSaving(false);
    }
  };

  if (view.kind === "loading") {
    return (
      <FormCard>
        <Box role="status" sx={{ display: "flex", alignItems: "center", gap: 2, py: 2 }}>
          <CircularProgress size={24} />
          <Typography>Sprawdzamy link…</Typography>
        </Box>
      </FormCard>
    );
  }

  if (view.kind === "load_error") {
    return (
      <FormCard>
        <StepHeading focus={false}>Nie udało się sprawdzić linku</StepHeading>
        <Alert severity="error" sx={{ mb: 3 }}>
          {view.message}
        </Alert>
        <Button variant="contained" size="large" onClick={() => void check()}>
          Spróbuj ponownie
        </Button>
      </FormCard>
    );
  }

  if (view.kind === "done") {
    return (
      <FormCard>
        <Box sx={{ textAlign: "center" }}>
          <CheckCircleOutline aria-hidden="true" sx={{ fontSize: 56, color: "success.main", mb: 1 }} />
          <StepHeading focus={acted}>Hasło zmienione. Możesz się zalogować.</StepHeading>
          <Typography sx={{ color: "grey.700", mb: 3 }}>
            Konto zostało wylogowane na wszystkich urządzeniach. Zaloguj się nowym hasłem.
          </Typography>
          <Button component={Link} href="/login" variant="contained" size="large" sx={{ width: { xs: "100%", sm: "auto" } }}>
            Przejdź do logowania
          </Button>
        </Box>
      </FormCard>
    );
  }

  if (view.kind === "problem") {
    const text = {
      expired: {
        title: "Ten link wygasł",
        body: "Link do zmiany hasła działa przez godzinę. Poproś o nowy — wyślemy go rodzicowi.",
      },
      used: {
        title: "Ten link został już wykorzystany",
        body: "Hasło zostało już zmienione tym linkiem. Jeśli trzeba zmienić je jeszcze raz, poproś o nowy link.",
      },
      invalid: {
        title: "Ten link nie działa",
        body: "Link jest nieprawidłowy albo konto zostało usunięte. Możesz poprosić o nowy link.",
      },
    }[view.state];
    return (
      <FormCard>
        <StepHeading focus={acted}>{text.title}</StepHeading>
        <Typography sx={{ color: "grey.700", mb: 3 }}>{text.body}</Typography>
        <Button component={Link} href="/reset-hasla" variant="contained" size="large" sx={{ width: { xs: "100%", sm: "auto" } }}>
          Poproś o nowy link
        </Button>
      </FormCard>
    );
  }

  return (
    <FormCard>
      <StepHeading focus={false}>Ustaw nowe hasło</StepHeading>
      <Typography sx={{ color: "grey.700", mb: 3 }}>
        Konto: <strong>{view.login}</strong>
      </Typography>
      <Box component="form" noValidate onSubmit={submit}>
        {/* Ukryte pole z loginem pomaga menedzerom hasel zapisac dane do wlasciwego konta */}
        <input type="text" name="username" autoComplete="username" value={view.login} readOnly hidden />
        <PasswordField
          id="reset-new-password"
          label="Nowe hasło"
          value={password}
          onChange={(value) => {
            setPassword(value);
            setFieldError(null);
          }}
          autoComplete="new-password"
          error={fieldError}
          helperText="Co najmniej 8 znaków. Najłatwiej zapamiętać kilka słów, np. „zielony rower w lesie”."
          disabled={saving}
        />
        <Box aria-live="assertive">
          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
        </Box>
        <Box sx={{ mt: 3 }}>
          <SubmitButton busy={saving} busyLabel="Zapisywanie…">
            Zapisz nowe hasło
          </SubmitButton>
        </Box>
      </Box>
    </FormCard>
  );
}
