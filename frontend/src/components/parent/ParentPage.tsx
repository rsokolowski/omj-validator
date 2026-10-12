"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Paper,
  Typography,
} from "@mui/material";
import { APIError } from "@/lib/api/client";
import { errorText, parentApi } from "@/lib/api/account";
import type { ParentChild } from "@/lib/types";
import { formatDateShort } from "@/lib/utils/dates";
import { formatDayPl, passwordProblem } from "@/lib/utils/account";
import { FormCard } from "@/components/account/FormCard";
import { StepHeading } from "@/components/account/StepHeading";
import { ConfirmDialog } from "@/components/account/ConfirmDialog";
import { PasswordField } from "@/components/account/PasswordField";
import { ParentLinkRequest } from "./ParentLinkRequest";
import { forgetLinkToken, LinkTokenLoading, useLinkToken } from "@/components/account/LinkToken";

type View =
  | { kind: "loading" }
  | { kind: "load_error"; message: string }
  | { kind: "expired" }
  | { kind: "invalid" }
  | { kind: "list"; parentEmail: string; children: ParentChild[] }
  | { kind: "all_deleted" };

/** 410 = link expired, 404 = invalid (backend answers with `state`) */
function linkProblem(error: unknown): "expired" | "invalid" | null {
  if (!(error instanceof APIError)) return null;
  if (error.status === 410 || error.state === "expired") return "expired";
  if (error.status === 404 && error.state === "invalid") return "invalid";
  return null;
}

function ParentPageView({ token }: { token: string | null }) {
  const [view, setView] = useState<View>(token ? { kind: "loading" } : { kind: "invalid" });
  const [acted, setActed] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  // Zwiekszany przyciskiem "Sprobuj ponownie"
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    parentApi
      .children(token)
      .then((data) => {
        if (!cancelled) setView({ kind: "list", parentEmail: data.parent_email, children: data.children });
      })
      .catch((error) => {
        if (cancelled) return;
        const problem = linkProblem(error);
        setView(problem ? { kind: problem } : { kind: "load_error", message: errorText(error) });
      });
    return () => {
      cancelled = true;
    };
  }, [token, attempt]);

  const retry = () => {
    setView({ kind: "loading" });
    setAttempt((n) => n + 1);
  };

  if (!token) {
    return (
      <FormCard>
        <StepHeading focus={false}>Strona rodzica</StepHeading>
        <Typography sx={{ color: "grey.700", mb: 2 }}>
          Tutaj zobaczysz konta swoich dzieci w Trenerze OMJ. Możesz usunąć konto albo ustawić
          dziecku nowe hasło.
        </Typography>
        <ParentLinkRequest />
      </FormCard>
    );
  }

  if (view.kind === "loading") {
    return (
      <FormCard>
        <Box role="status" sx={{ display: "flex", alignItems: "center", gap: 2, py: 2 }}>
          <CircularProgress size={24} />
          <Typography>Wczytujemy konta…</Typography>
        </Box>
      </FormCard>
    );
  }

  if (view.kind === "load_error") {
    return (
      <FormCard>
        <StepHeading focus={false}>Nie udało się wczytać strony</StepHeading>
        <Alert severity="error" sx={{ mb: 3 }}>
          {view.message}
        </Alert>
        <Button variant="contained" size="large" onClick={retry}>
          Spróbuj ponownie
        </Button>
      </FormCard>
    );
  }

  if (view.kind === "expired" || view.kind === "invalid") {
    return (
      <FormCard>
        <StepHeading focus={acted}>
          {view.kind === "expired" ? "Ten link wygasł" : "Ten link nie działa"}
        </StepHeading>
        <Typography sx={{ color: "grey.700", mb: 2 }}>
          {view.kind === "expired"
            ? "Link do strony rodzica działa przez 30 dni. Możemy wysłać Ci nowy."
            : "Link jest nieprawidłowy albo konta dzieci zostały już usunięte. Możemy wysłać Ci nowy link."}
        </Typography>
        <ParentLinkRequest />
      </FormCard>
    );
  }

  if (view.kind === "all_deleted") {
    return (
      <FormCard>
        <StepHeading focus>Konto zostało usunięte</StepHeading>
        <Typography sx={{ color: "grey.700" }}>
          Usunęliśmy konto razem ze wszystkimi danymi. Nie ma tu już innych kont, więc ten link
          przestał działać.
        </Typography>
      </FormCard>
    );
  }

  const onDeleted = (child: ParentChild, remaining: number) => {
    if (remaining <= 0) {
      // Nie ma juz kont pod tym adresem - link nie jest potrzebny
      forgetLinkToken();
      setView({ kind: "all_deleted" });
      return;
    }
    setView({
      ...view,
      children: view.children.filter((c) => c.id !== child.id),
    });
    setNotice(`Konto ${child.identifier} zostało usunięte razem ze wszystkimi danymi.`);
  };

  const onLinkProblem = (problem: "expired" | "invalid") => {
    setActed(true);
    setView({ kind: problem });
  };

  return (
    <FormCard wide>
      <StepHeading focus={false}>Konta Twoich dzieci</StepHeading>
      <Typography sx={{ color: "grey.700", mb: 3 }}>
        Twój adres: <strong>{view.parentEmail}</strong>
      </Typography>

      <Box aria-live="polite">
        {notice && (
          <Alert severity="success" sx={{ mb: 3 }} onClose={() => setNotice(null)}>
            {notice}
          </Alert>
        )}
      </Box>

      <Box component="ul" sx={{ listStyle: "none", p: 0, m: 0, display: "flex", flexDirection: "column", gap: 2 }}>
        {view.children.map((child) => (
          <li key={child.id}>
            <ChildCard
              token={token}
              child={child}
              onDeleted={(remaining) => onDeleted(child, remaining)}
              onLinkProblem={onLinkProblem}
            />
          </li>
        ))}
      </Box>
    </FormCard>
  );
}

interface ChildCardProps {
  token: string;
  child: ParentChild;
  onDeleted: (remaining: number) => void;
  onLinkProblem: (problem: "expired" | "invalid") => void;
}

function ChildCard({ token, child, onDeleted, onLinkProblem }: ChildCardProps) {
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [passwordChanged, setPasswordChanged] = useState(false);
  const pending = child.status === "pending_parent";

  const remove = async () => {
    if (deleting) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      const result = await parentApi.deleteChild(token, child.id);
      setDeleteOpen(false);
      onDeleted(result.remaining);
    } catch (error) {
      const problem = linkProblem(error);
      if (problem) {
        setDeleteOpen(false);
        onLinkProblem(problem);
      } else {
        setDeleteError(errorText(error));
      }
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Paper variant="outlined" sx={{ p: { xs: 2, sm: 2.5 }, borderColor: "grey.200" }}>
      <Box sx={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 1.5, mb: 1 }}>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="body2" sx={{ color: "grey.600" }}>
            {child.identifier_label}
          </Typography>
          <Typography
            component="h2"
            sx={{ fontWeight: 700, fontSize: "1.125rem", color: "grey.900", wordBreak: "break-all" }}
          >
            {child.identifier}
          </Typography>
        </Box>
        <Chip
          label={pending ? "Czeka na Twoją zgodę" : "Aktywne"}
          size="small"
          sx={{
            alignSelf: "flex-start",
            fontWeight: 600,
            bgcolor: pending ? "#fffbeb" : "#ecfdf5",
            color: pending ? "#92400e" : "success.main",
            border: "1px solid",
            borderColor: pending ? "#fde68a" : "#a7f3d0",
          }}
        />
      </Box>

      <Typography variant="body2" sx={{ color: "grey.600" }}>
        Konto założone {formatDateShort(child.created_at)}
      </Typography>

      {pending && (
        <Typography variant="body2" sx={{ color: "grey.700", mt: 1.5 }}>
          Zgodę wyrazisz przyciskiem w wiadomości „Prośba o zgodę”.
          {child.pending_deadline && (
            <> Bez zgody konto zostanie usunięte {formatDayPl(child.pending_deadline)}.</>
          )}
        </Typography>
      )}

      <Box aria-live="polite">
        {passwordChanged && (
          <Alert severity="success" sx={{ mt: 2 }}>
            Hasło zmienione. Dziecko zaloguje się nowym hasłem.
          </Alert>
        )}
      </Box>

      <Box sx={{ mt: 2, display: "flex", flexDirection: { xs: "column", sm: "row" }, gap: 1.5 }}>
        {child.kind === "login" && (
          <Button
            variant="outlined"
            onClick={() => {
              setPasswordChanged(false);
              setPasswordOpen(true);
            }}
            sx={{ py: 1.25 }}
          >
            Ustaw nowe hasło
          </Button>
        )}
        <Button
          variant="outlined"
          color="error"
          onClick={() => {
            setDeleteError(null);
            setDeleteOpen(true);
          }}
          sx={{ py: 1.25 }}
        >
          Usuń konto i wszystkie dane
        </Button>
      </Box>

      <ConfirmDialog
        open={deleteOpen}
        id={`delete-${child.id}`}
        title="Usunąć konto na zawsze?"
        confirmLabel="Usuń konto na zawsze"
        busyLabel="Usuwanie…"
        busy={deleting}
        error={deleteError}
        onConfirm={() => void remove()}
        onClose={() => setDeleteOpen(false)}
      >
        <Typography sx={{ color: "grey.700", mb: 1.5 }}>
          Usuniemy konto <strong>{child.identifier}</strong> i wszystko, co dziecko w nim zapisało:
          rozwiązania, zdjęcia i postępy. Tej operacji nie da się cofnąć.
        </Typography>
        <Typography sx={{ color: "grey.700" }}>
          Usunięcie konta oznacza też wycofanie Twojej zgody.
        </Typography>
      </ConfirmDialog>

      {child.kind === "login" && (
        <PasswordDialog
          open={passwordOpen}
          token={token}
          child={child}
          onClose={() => setPasswordOpen(false)}
          onChanged={() => {
            setPasswordOpen(false);
            setPasswordChanged(true);
          }}
          onLinkProblem={(problem) => {
            setPasswordOpen(false);
            onLinkProblem(problem);
          }}
        />
      )}
    </Paper>
  );
}

interface PasswordDialogProps {
  open: boolean;
  token: string;
  child: ParentChild;
  onClose: () => void;
  onChanged: () => void;
  onLinkProblem: (problem: "expired" | "invalid") => void;
}

function PasswordDialog({ open, token, child, onClose, onChanged, onLinkProblem }: PasswordDialogProps) {
  const [password, setPassword] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const titleId = `password-${child.id}-title`;

  const close = () => {
    if (saving) return;
    setPassword("");
    setFieldError(null);
    setError(null);
    onClose();
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (saving) return;
    const problem = passwordProblem(password, child.identifier);
    if (problem) {
      setFieldError(problem);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await parentApi.setPassword(token, child.id, password);
      setPassword("");
      onChanged();
    } catch (err) {
      const link = linkProblem(err);
      if (link) onLinkProblem(link);
      else if (err instanceof APIError && err.field === "password") setFieldError(err.message);
      else setError(errorText(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      aria-labelledby={titleId}
      maxWidth="sm"
      fullWidth
      sx={{ "& .MuiDialog-paper": { mx: 2, width: "calc(100% - 32px)" } }}
    >
      <Box component="form" noValidate onSubmit={submit}>
        <DialogTitle id={titleId} sx={{ fontWeight: 700 }}>
          Nowe hasło dla {child.identifier}
        </DialogTitle>
        <DialogContent>
          <Typography sx={{ color: "grey.700", mb: 2.5 }}>
            Dziecko zostanie wylogowane na wszystkich urządzeniach i zaloguje się nowym hasłem.
          </Typography>
          <PasswordField
            id={`password-${child.id}`}
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
            autoFocus
          />
          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
        </DialogContent>
        <DialogActions
          sx={{
            px: 3,
            pb: 2.5,
            gap: 1,
            flexDirection: { xs: "column-reverse", sm: "row" },
            alignItems: "stretch",
            "& > :not(style) ~ :not(style)": { ml: { xs: 0, sm: 1 } },
          }}
        >
          <Button type="button" onClick={close} disabled={saving} sx={{ py: 1.25 }}>
            Anuluj
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={saving}
            aria-busy={saving || undefined}
            startIcon={saving ? <CircularProgress size={16} color="inherit" /> : undefined}
            sx={{ py: 1.25 }}
          >
            {saving ? "Zapisywanie…" : "Zapisz hasło"}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}

/** Odczytuje token z linku (i chowa go z paska adresu), potem pokazuje strone. */
export function ParentPage({ token: tokenFromUrl }: { token: string | null }) {
  const link = useLinkToken(tokenFromUrl);
  if (!link.ready) return <LinkTokenLoading />;
  return <ParentPageView token={link.token} />;
}
