"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Alert, Box, Button, CircularProgress, Link as MuiLink, Typography } from "@mui/material";
import MarkEmailUnreadOutlined from "@mui/icons-material/MarkEmailUnreadOutlined";
import CheckCircleOutline from "@mui/icons-material/CheckCircleOutline";
import Send from "@mui/icons-material/Send";
import { APIError } from "@/lib/api/client";
import { accountApi, errorText } from "@/lib/api/account";
import { useAuth } from "@/lib/hooks/useAuth";
import type { AuthMeResponse, ResendResponse } from "@/lib/types";
import { emailProblem, formatDayPl, normalizeEmail, secondsUntil } from "@/lib/utils/account";
import { FormCard } from "./FormCard";
import { StepHeading } from "./StepHeading";
import { ParentEmailField } from "./ParentEmailField";
import { SubmitButton } from "./SubmitButton";

const POLL_MS = 10_000;
// Serwer pozwala wyslac kolejna wiadomosc po 60 s (CONSENT_COOLDOWN)
const COOLDOWN_MAX_S = 60;

/**
 * Odpytujemy tylko, dopoki konto czeka na zgode. `latest` jest puste, gdy
 * pamiec SWR ma jeszcze tylko fallbackData - wtedy tez odpytujemy.
 * Funkcja poza komponentem: nowa funkcja przy kazdym renderze (odliczanie
 * renderuje co sekunde) restartowalaby licznik SWR i odpytanie nigdy by nie nastapilo.
 */
function pollInterval(latest?: AuthMeResponse): number {
  return !latest || (latest.is_authenticated && latest.account?.status === "pending_parent") ? POLL_MS : 0;
}

type Notice = { severity: "success" | "info" | "error"; text: string } | null;

interface PendingAccountProps {
  initial: AuthMeResponse;
}

export function PendingAccount({ initial }: PendingAccountProps) {
  const router = useRouter();
  // Czy strona zaczela od oczekiwania (wtedy "Rodzic potwierdzil konto!")
  const [wasPending] = useState(initial.account?.status === "pending_parent");
  const { data, refetch } = useAuth({
    fallbackData: initial,
    revalidateOnFocus: true,
    refreshInterval: pollInterval,
  });

  const account = data?.account ?? null;
  const pending = account?.status === "pending_parent" ? account.pending : null;
  const isActive = account?.status === "active" && !account.needs_profile;
  const signedOut = data ? !data.is_authenticated : false;

  // Odliczanie do "Wyslij ponownie". null = jeszcze przed montazem (bez rozjazdu
  // miedzy HTML z serwera a pierwszym renderem w przegladarce).
  const [now, setNow] = useState<number | null>(null);
  const [localCooldownUntil, setLocalCooldownUntil] = useState<number | null>(null);
  const [sending, setSending] = useState(false);
  const [limitReached, setLimitReached] = useState(false);
  const [notice, setNotice] = useState<Notice>(null);
  const [editing, setEditing] = useState(false);

  const serverRemaining = now === null ? 0 : secondsUntil(pending?.resend_available_at ?? null, now, COOLDOWN_MAX_S);
  const localRemaining =
    now === null || localCooldownUntil === null
      ? 0
      : Math.min(COOLDOWN_MAX_S, Math.max(0, Math.ceil((localCooldownUntil - now) / 1000)));
  const remaining = Math.max(serverRemaining, localRemaining);

  // Zegar: pierwszy odczyt po zamontowaniu, potem co sekunde w trakcie odliczania
  const ticking = now === null || remaining > 0;
  useEffect(() => {
    if (!ticking) return;
    const update = () => setNow(Date.now());
    const first = window.setTimeout(update, 0);
    const timer = window.setInterval(update, 1000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [ticking]);

  const needsProfile = account?.needs_profile ?? false;
  useEffect(() => {
    if (needsProfile) router.replace("/konto/uzupelnij");
  }, [needsProfile, router]);

  const applyResult = (result: ResendResponse) => {
    if (data && result.account) {
      void refetch({ ...data, account: result.account }, { revalidate: false });
    }
    setLocalCooldownUntil(Date.now() + COOLDOWN_MAX_S * 1000);
    setNow(Date.now());
  };

  const handleSendError = (error: unknown): string | null => {
    if (error instanceof APIError) {
      if (error.code === "email_limit") {
        setLimitReached(true);
        return null;
      }
      if (error.code === "email_cooldown" && error.retryAfter) {
        setLocalCooldownUntil(Date.now() + error.retryAfter * 1000);
        setNow(Date.now());
      }
    }
    return errorText(error);
  };

  const resend = async () => {
    if (sending || remaining > 0 || limitReached) return;
    setSending(true);
    setNotice(null);
    try {
      const result = await accountApi.resendConsent();
      applyResult(result);
      setNotice({
        severity: "success",
        text: `Wysłaliśmy wiadomość na adres ${result.account?.pending?.parent_email ?? pending?.parent_email ?? ""}.`,
      });
    } catch (error) {
      const message = handleSendError(error);
      if (message) setNotice({ severity: "error", text: message });
    } finally {
      setSending(false);
    }
  };

  // ------------------------------------------------------------- states other than pending

  if (signedOut) {
    return (
      <FormCard>
        <StepHeading focus={wasPending}>Konto nie jest już dostępne</StepHeading>
        <Typography sx={{ color: "grey.700", mb: 3 }}>
          Sesja się skończyła albo konto zostało usunięte — na przykład dlatego, że rodzic nie
          zgodził się na jego założenie. Jeśli to pomyłka, porozmawiaj z rodzicem i załóż konto
          jeszcze raz.
        </Typography>
        <Box sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 1.5 }}>
          <Button component={Link} href="/login" variant="contained" size="large">
            Zaloguj się
          </Button>
          <Button component={Link} href="/rejestracja" variant="outlined" size="large">
            Załóż konto
          </Button>
        </Box>
      </FormCard>
    );
  }

  if (isActive || !pending) {
    const confirmedNow = wasPending && isActive;
    return (
      <FormCard>
        <Box sx={{ textAlign: "center" }}>
          <CheckCircleOutline aria-hidden="true" sx={{ fontSize: 56, color: "success.main", mb: 1 }} />
          <StepHeading focus={confirmedNow}>
            {confirmedNow ? "Rodzic potwierdził konto!" : "Twoje konto jest aktywne"}
          </StepHeading>
          <Typography sx={{ color: "grey.700", mb: 3 }}>
            Możesz już przesyłać rozwiązania i śledzić swoje postępy. Powodzenia!
          </Typography>
          <Button component={Link} href="/years" variant="contained" size="large" sx={{ width: { xs: "100%", sm: "auto" } }}>
            Przejdź do zadań
          </Button>
        </Box>
      </FormCard>
    );
  }

  // ------------------------------------------------------------- pending

  const sent = Boolean(pending.last_sent_at);
  const resendLabel = sent ? "Wyślij ponownie" : "Wyślij wiadomość";

  return (
    <FormCard>
      <Box
        aria-hidden="true"
        sx={{
          width: 56,
          height: 56,
          borderRadius: "50%",
          bgcolor: "#eff6ff",
          color: "primary.main",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          mb: 2,
        }}
      >
        <MarkEmailUnreadOutlined sx={{ fontSize: 30 }} />
      </Box>
      <StepHeading focus={false}>Prawie gotowe! Czekamy na zgodę rodzica</StepHeading>

      {sent ? (
        <Typography sx={{ color: "grey.700", mb: 2 }}>
          Wysłaliśmy wiadomość na adres <strong>{pending.parent_email}</strong>. Poproś rodzica,
          żeby ją otworzył i kliknął „Wyrażam zgodę”. Sprawdźcie też folder Spam / Oferty.
        </Typography>
      ) : (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Wiadomość do rodzica (<strong>{pending.parent_email}</strong>) jeszcze nie wyszła.
          Kliknij „Wyślij wiadomość”, żeby spróbować jeszcze raz.
        </Alert>
      )}

      <Box sx={{ bgcolor: "grey.50", borderRadius: 2, p: 2, mb: 3 }}>
        <Typography variant="body2" sx={{ color: "grey.700" }}>
          Do tego czasu możesz{" "}
          <MuiLink component={Link} href="/years" sx={{ color: "primary.main" }}>
            przeglądać zadania
          </MuiLink>{" "}
          i wskazówki. Rozwiązania prześlesz, gdy rodzic się zgodzi. Ta strona odświeży się sama.
        </Typography>
      </Box>

      {!editing && (
        <Box sx={{ display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 1.5, flexWrap: "wrap" }}>
          <Button
            variant={sent ? "outlined" : "contained"}
            size="large"
            onClick={resend}
            disabled={sending || remaining > 0 || limitReached || now === null}
            aria-busy={sending || undefined}
            startIcon={sending ? <CircularProgress size={18} color="inherit" /> : <Send />}
            sx={{ py: 1.25 }}
          >
            {sending ? "Wysyłanie…" : remaining > 0 ? `${resendLabel} (za ${remaining} s)` : resendLabel}
          </Button>
          <Button
            variant="text"
            size="large"
            onClick={() => {
              setNotice(null);
              setEditing(true);
            }}
            sx={{ py: 1.25 }}
          >
            Zmień adres e-mail rodzica
          </Button>
        </Box>
      )}

      {editing && (
        <ChangeParentEmailForm
          blocked={limitReached}
          onCancel={() => setEditing(false)}
          onSent={(result) => {
            applyResult(result);
            setEditing(false);
            setNotice({
              severity: "success",
              text: `Zmieniliśmy adres i wysłaliśmy wiadomość na ${result.account?.pending?.parent_email ?? "nowy adres"}.`,
            });
          }}
          onError={handleSendError}
        />
      )}

      <Box aria-live="polite" sx={{ mt: notice || limitReached ? 2 : 0 }}>
        {limitReached && <Alert severity="info">Wysłaliśmy już kilka wiadomości. Spróbuj jutro.</Alert>}
        {notice && !limitReached && <Alert severity={notice.severity}>{notice.text}</Alert>}
      </Box>

      {pending.deadline && (
        <Alert severity="info" variant="outlined" sx={{ mt: 3, color: "grey.800" }}>
          Jeśli rodzic nie potwierdzi konta do <strong>{formatDayPl(pending.deadline)}</strong>,
          usuniemy je razem ze wszystkimi danymi.
        </Alert>
      )}

      <Box sx={{ mt: 3, pt: 2, borderTop: 1, borderColor: "grey.200" }}>
        {/* Zwykly <a>: prefetch Next.js wylogowalby uzytkownika */}
        <Button href="/logout" variant="text" sx={{ color: "grey.700", py: 1.25 }}>
          Wyloguj
        </Button>
      </Box>
    </FormCard>
  );
}

interface ChangeParentEmailFormProps {
  blocked: boolean;
  onCancel: () => void;
  onSent: (result: ResendResponse) => void;
  /** Returns the message to show, or null when the caller shows it elsewhere */
  onError: (error: unknown) => string | null;
}

function ChangeParentEmailForm({ blocked, onCancel, onSent, onError }: ChangeParentEmailFormProps) {
  const [value, setValue] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (saving) return;
    const email = normalizeEmail(value);
    const problem = emailProblem(email);
    if (problem) {
      setFieldError(problem);
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      onSent(await accountApi.changeParentEmail(email));
    } catch (error) {
      setSaving(false);
      if (error instanceof APIError && error.field === "parent_email") {
        setFieldError(error.message);
        return;
      }
      const message = onError(error);
      if (message) setFormError(message);
      else onCancel();
    }
  };

  return (
    <Box
      component="form"
      noValidate
      onSubmit={submit}
      aria-label="Zmiana adresu e-mail rodzica"
      sx={{ border: "1px solid", borderColor: "grey.200", borderRadius: 2, p: 2 }}
    >
      <Typography variant="body2" sx={{ color: "grey.700", mb: 2 }}>
        Wpisz poprawny adres. Wyślemy na niego nową wiadomość, a link ze starej przestanie działać.
      </Typography>
      <ParentEmailField
        id="new-parent-email"
        value={value}
        onChange={(v) => {
          setValue(v);
          setFieldError(null);
        }}
        error={fieldError}
        disabled={saving || blocked}
        autoFocus
      />
      {formError && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {formError}
        </Alert>
      )}
      <Box
        sx={{
          mt: 2,
          display: "flex",
          flexDirection: { xs: "column-reverse", sm: "row" },
          justifyContent: "flex-end",
          gap: 1.5,
        }}
      >
        <Button type="button" onClick={onCancel} disabled={saving} sx={{ py: 1.25 }}>
          Anuluj
        </Button>
        <SubmitButton busy={saving} busyLabel="Wysyłanie…" disabled={blocked}>
          Zapisz i wyślij
        </SubmitButton>
      </Box>
    </Box>
  );
}
