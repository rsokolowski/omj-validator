"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Link as MuiLink,
  Typography,
} from "@mui/material";
import CheckCircleOutline from "@mui/icons-material/CheckCircleOutline";
import { APIError } from "@/lib/api/client";
import { errorText, parentApi } from "@/lib/api/account";
import type { ConsentView, ParentChild } from "@/lib/types";
import { formatDayPl } from "@/lib/utils/account";
import { FormCard } from "@/components/account/FormCard";
import { StepHeading } from "@/components/account/StepHeading";
import { ConfirmDialog } from "@/components/account/ConfirmDialog";
import { ChildIdentifier } from "./ChildIdentifier";
import { forgetLinkToken, LinkTokenLoading, useLinkToken } from "@/components/account/LinkToken";

type View =
  | { kind: "loading" }
  | { kind: "load_error"; message: string }
  | { kind: "link"; data: ConsentView }
  | { kind: "accepted"; manageUrl: string; child: ParentChild }
  | { kind: "declined" };

interface ParentConsentProps {
  token: string | null;
  /** ?decyzja=nie - the parent clicked "Nie zgadzam się" in the e-mail */
  declineIntent: boolean;
}

/**
 * Strona zgody rodzica. Samo otwarcie strony niczego nie zmienia (skanery
 * poczty otwieraja linki) - decyzja zapada dopiero po kliknieciu przycisku.
 */
function ParentConsentView({ token, declineIntent }: ParentConsentProps) {
  const [view, setView] = useState<View>(token ? { kind: "loading" } : { kind: "load_error", message: "" });
  // Fokus na naglowek przy zmianie stanu po akcji, nie przy pierwszym wejsciu
  const [acted, setActed] = useState(false);
  const [busy, setBusy] = useState<"accept" | "decline" | "resend" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [resent, setResent] = useState(false);
  const autoOpened = useRef(false);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const data = await parentApi.consent(token);
      setView({ kind: "link", data });
      if (declineIntent && data.state === "valid" && !autoOpened.current) {
        autoOpened.current = true;
        setDialogOpen(true);
      }
    } catch (error) {
      setView({ kind: "load_error", message: errorText(error) });
    }
  }, [token, declineIntent]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- Fetch on mount; state is set after the await
    void load();
  }, [load]);

  const decide = async (decision: "accept" | "decline") => {
    if (!token || busy) return;
    setBusy(decision);
    setActionError(null);
    try {
      const result = await parentApi.decide(token, decision);
      // Decyzja zapadla - link nie jest juz potrzebny w tym wpisie historii
      forgetLinkToken();
      setActed(true);
      setDialogOpen(false);
      setView(
        result.result === "accepted"
          ? { kind: "accepted", manageUrl: result.manage_url, child: result.child }
          : { kind: "declined" }
      );
    } catch (error) {
      if (error instanceof APIError && error.status === 410) {
        // Link przestal dzialac w miedzyczasie - pokaz aktualny stan
        setActed(true);
        setDialogOpen(false);
        await load();
      } else {
        setActionError(errorText(error));
      }
    } finally {
      setBusy(null);
    }
  };

  const resend = async () => {
    if (!token || busy) return;
    setBusy("resend");
    setActionError(null);
    try {
      await parentApi.resendConsent(token);
      setResent(true);
    } catch (error) {
      setActionError(errorText(error));
    } finally {
      setBusy(null);
    }
  };

  if (view.kind === "loading") {
    return (
      <FormCard>
        <Box role="status" sx={{ display: "flex", alignItems: "center", gap: 2, py: 2 }}>
          <CircularProgress size={24} />
          <Typography>Wczytujemy informacje o koncie…</Typography>
        </Box>
      </FormCard>
    );
  }

  if (view.kind === "load_error") {
    if (!token) return <LinkProblem state="invalid" />;
    return (
      <FormCard>
        <StepHeading focus={false}>Nie udało się wczytać strony</StepHeading>
        <Alert severity="error" sx={{ mb: 3 }}>
          {view.message}
        </Alert>
        <Button variant="contained" size="large" onClick={() => void load()}>
          Spróbuj ponownie
        </Button>
      </FormCard>
    );
  }

  if (view.kind === "accepted") {
    return (
      <FormCard>
        <Box sx={{ textAlign: "center" }}>
          <CheckCircleOutline aria-hidden="true" sx={{ fontSize: 56, color: "success.main", mb: 1 }} />
          <StepHeading focus={acted}>Dziękujemy! Konto jest aktywne.</StepHeading>
          <Typography sx={{ color: "grey.700", mb: 1 }}>
            Dziecko może już przesyłać rozwiązania.
          </Typography>
          <Typography sx={{ color: "grey.700", mb: 3 }}>
            Wysłaliśmy Ci też e-mail z linkiem do strony rodzica. Tam w każdej chwili usuniesz
            konto{view.child.kind === "login" ? " albo ustawisz dziecku nowe hasło" : ""}.
          </Typography>
          <Button
            component={Link}
            href={view.manageUrl}
            variant="contained"
            size="large"
            sx={{ width: { xs: "100%", sm: "auto" } }}
          >
            Przejdź do strony rodzica
          </Button>
        </Box>
      </FormCard>
    );
  }

  if (view.kind === "declined") {
    return (
      <FormCard>
        <StepHeading focus={acted}>Konto zostało usunięte</StepHeading>
        <Typography sx={{ color: "grey.700", mb: 1 }}>
          Usunęliśmy konto dziecka i wszystkie zapisane w nim dane. Dziękujemy za odpowiedź.
        </Typography>
        <Typography variant="body2" sx={{ color: "grey.700" }}>
          Twój adres e-mail, jeśli nie jest powiązany z kontem innego dziecka, usuniemy w ciągu
          dwóch dób (tyle potrzebują limity wysyłki wiadomości). Przez
          pewien czas zostają jeszcze ślady techniczne bez danych dziecka, np. w kopiach
          zapasowych &ndash; opisujemy je w{" "}
          <MuiLink component={Link} href="/regulamin" target="_blank" rel="noopener noreferrer" sx={{ color: "primary.main" }}>
            regulaminie, w punkcie 11
          </MuiLink>
          .
        </Typography>
      </FormCard>
    );
  }

  const { data } = view;
  const child = data.child;

  if (data.state !== "valid" || !child) {
    return (
      <LinkProblem
        state={data.state === "valid" ? "invalid" : data.state}
        focus={acted}
        child={child}
        canResend={data.can_resend}
        resent={resent}
        resending={busy === "resend"}
        onResend={resend}
        error={actionError}
      />
    );
  }

  const { summary } = data;

  return (
    <FormCard>
      <StepHeading focus={acted}>Prośba o zgodę na konto dziecka</StepHeading>
      <Typography sx={{ color: "grey.700", mb: 2.5 }}>
        Trener OMJ to bezpłatny, niekomercyjny serwis do ćwiczenia zadań z Olimpiady Matematycznej
        Juniorów. Ktoś założył w nim konto i podał Twój adres jako adres rodzica lub opiekuna.
      </Typography>

      <ChildIdentifier child={child} />

      <Typography variant="h6" component="h2" sx={{ fontWeight: 600, color: "grey.900", mt: 3, mb: 1 }}>
        Na co się zgadzasz
      </Typography>
      <Box component="ul" sx={{ pl: 2.5, m: 0, color: "grey.700", "& li": { mb: 1 } }}>
        <li>
          Dziecko może przesyłać zdjęcia albo wpisane rozwiązania zadań. Ocenia je automatycznie
          model sztucznej inteligencji (AI).
        </li>
        <li>
          Do oceny wysyłamy zdjęcia i rozwiązania do firmy Google (Gemini) w USA, a zapasowo (np. gdy
          usługa Google nie działa) do firmy Anthropic (Claude), również w USA. Nie wysyłamy tam imienia,
          nazwiska ani adresu e-mail dziecka.
        </li>
        <li>
          Rozwiązania przechowujemy przez {summary.submission_retention}. Konto, z którego nikt nie
          korzysta przez {summary.inactive_retention}, usuwamy automatycznie.
        </li>
        <li>
          W każdej chwili możesz usunąć konto dziecka razem ze wszystkimi danymi — na stronie
          rodzica, do której link dostaniesz e-mailem.
        </li>
      </Box>
      <Typography variant="body2" sx={{ mt: 1.5, color: "grey.700" }}>
        Szczegóły:{" "}
        <MuiLink component={Link} href="/regulamin" target="_blank" rel="noopener noreferrer" sx={{ color: "primary.main" }}>
          regulamin i zasady prywatności
        </MuiLink>
        .
      </Typography>

      {child.pending_deadline && (
        <Typography variant="body2" sx={{ mt: 2, color: "grey.700" }}>
          Jeśli nic nie zrobisz, konto zostanie usunięte {formatDayPl(child.pending_deadline)}.
        </Typography>
      )}

      {declineIntent && (
        <Alert severity="info" sx={{ mt: 3 }}>
          W wiadomości wybrano „Nie zgadzam się”. Aby usunąć konto, potwierdź to przyciskiem poniżej.
        </Alert>
      )}

      <Box aria-live="assertive">
        {actionError && !dialogOpen && (
          <Alert severity="error" sx={{ mt: 3 }}>
            {actionError}
          </Alert>
        )}
      </Box>

      <Box
        sx={{
          mt: 3,
          display: "flex",
          flexDirection: { xs: "column", sm: "row" },
          gap: 1.5,
        }}
      >
        <Button
          variant="contained"
          size="large"
          onClick={() => void decide("accept")}
          disabled={busy !== null}
          aria-busy={busy === "accept" || undefined}
          startIcon={busy === "accept" ? <CircularProgress size={18} color="inherit" /> : undefined}
          sx={{ py: 1.5, px: 4 }}
        >
          {busy === "accept" ? "Zapisywanie…" : "Wyrażam zgodę"}
        </Button>
        <Button
          variant="outlined"
          color="error"
          size="large"
          onClick={() => {
            setActionError(null);
            setDialogOpen(true);
          }}
          disabled={busy !== null}
          sx={{ py: 1.5 }}
        >
          Nie zgadzam się — usuń konto
        </Button>
      </Box>

      <ConfirmDialog
        open={dialogOpen}
        id="decline"
        title="Usunąć konto dziecka?"
        confirmLabel="Tak, usuń konto"
        busyLabel="Usuwanie…"
        busy={busy === "decline"}
        error={dialogOpen ? actionError : null}
        onConfirm={() => void decide("decline")}
        onClose={() => setDialogOpen(false)}
      >
        <Typography sx={{ color: "grey.700" }}>
          Konto <strong>{child.identifier}</strong> zostanie od razu usunięte razem ze wszystkim, co
          dziecko zdążyło zapisać. Tej operacji nie da się cofnąć.
        </Typography>
      </ConfirmDialog>
    </FormCard>
  );
}

interface LinkProblemProps {
  state: "expired" | "used" | "invalid";
  focus?: boolean;
  child?: ParentChild | null;
  canResend?: boolean;
  resent?: boolean;
  resending?: boolean;
  onResend?: () => void;
  error?: string | null;
}

function LinkProblem({ state, focus = false, child, canResend, resent, resending, onResend, error }: LinkProblemProps) {
  const parentPageLink = (
    <Button component={Link} href="/rodzic" variant="outlined" size="large" sx={{ width: { xs: "100%", sm: "auto" } }}>
      Przejdź do strony rodzica
    </Button>
  );

  if (state === "expired") {
    return (
      <FormCard>
        <StepHeading focus={focus}>Ten link wygasł</StepHeading>
        {canResend && child ? (
          <>
            <Typography sx={{ color: "grey.700", mb: 3 }}>
              Konto <strong>{child.identifier}</strong> wciąż czeka na Twoją decyzję. Wyślemy Ci
              nową wiadomość z aktualnym linkiem.
            </Typography>
            <Box aria-live="polite">
              {resent && (
                <Alert severity="success" sx={{ mb: 2 }}>
                  Wysłaliśmy nowy link. Sprawdź skrzynkę (także folder Spam).
                </Alert>
              )}
              {error && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {error}
                </Alert>
              )}
            </Box>
            {!resent && (
              <Button
                variant="contained"
                size="large"
                onClick={onResend}
                disabled={resending}
                aria-busy={resending || undefined}
                startIcon={resending ? <CircularProgress size={18} color="inherit" /> : undefined}
                sx={{ width: { xs: "100%", sm: "auto" } }}
              >
                {resending ? "Wysyłanie…" : "Wyślij nowy link"}
              </Button>
            )}
          </>
        ) : (
          <>
            <Typography sx={{ color: "grey.700", mb: 3 }}>
              Możliwe, że w skrzynce czeka już nowsza wiadomość od nas. Na stronie rodzica zobaczysz
              konta swoich dzieci i ich stan.
            </Typography>
            {parentPageLink}
          </>
        )}
      </FormCard>
    );
  }

  if (state === "used") {
    return (
      <FormCard>
        <StepHeading focus={focus}>Ten link został już wykorzystany</StepHeading>
        <Typography sx={{ color: "grey.700", mb: 3 }}>
          Decyzja w sprawie tego konta jest już zapisana. Jeśli chcesz zobaczyć konto dziecka albo
          je usunąć, przejdź na stronę rodzica.
        </Typography>
        {parentPageLink}
      </FormCard>
    );
  }

  return (
    <FormCard>
      <StepHeading focus={focus}>Ten link nie działa</StepHeading>
      <Typography sx={{ color: "grey.700", mb: 3 }}>
        Link jest nieprawidłowy albo konto zostało już usunięte. Jeśli adres był kopiowany z
        wiadomości, sprawdź, czy skopiował się w całości.
      </Typography>
      {parentPageLink}
    </FormCard>
  );
}

/** Odczytuje token z linku (i chowa go z paska adresu), potem pokazuje strone. */
export function ParentConsent({ token: tokenFromUrl, declineIntent }: ParentConsentProps) {
  const link = useLinkToken(tokenFromUrl);
  if (!link.ready) return <LinkTokenLoading />;
  return <ParentConsentView token={link.token} declineIntent={declineIntent} />;
}
