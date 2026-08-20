"use client";

import { useState } from "react";
import {
  Paper,
  Typography,
  Box,
  Button,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  TextField,
  CircularProgress,
} from "@mui/material";
import { fetchAPI } from "@/lib/api/client";
import { AccountDeleteResponse } from "@/lib/types";

interface DeleteAccountSectionProps {
  /** Fraza do przepisania - pochodzi z /api/auth/me, żeby nie mieć jej dwóch kopii
      (backend odrzuci każdą inną, więc nie wolno jej duplikować w kodzie UI). */
  confirmationPhrase: string;
}

export function DeleteAccountSection({ confirmationPhrase }: DeleteAccountSectionProps) {
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isPhraseValid = confirmation.trim() === confirmationPhrase;

  const openDialog = () => {
    setConfirmation("");
    setError(null);
    setIsDialogOpen(true);
  };

  const closeDialog = () => {
    if (isDeleting) return;
    setIsDialogOpen(false);
  };

  const handleDelete = async () => {
    if (!isPhraseValid || isDeleting) return;

    setIsDeleting(true);
    setError(null);

    try {
      await fetchAPI<AccountDeleteResponse>("/api/account/delete", {
        method: "POST",
        body: JSON.stringify({ confirmation: confirmationPhrase }),
      });
      // Twarde przeładowanie czyści stan klienta i cache SWR.
      window.location.href = "/";
    } catch (err) {
      setError(
        err instanceof Error && err.message
          ? err.message
          : "Nie udało się usunąć konta. Spróbuj ponownie później."
      );
      setIsDeleting(false);
    }
  };

  return (
    <Paper sx={{ p: 3, mt: 4, border: "1px solid", borderColor: "error.light" }}>
      <Typography
        variant="h6"
        component="h2"
        sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}
      >
        Twoje konto
      </Typography>

      <Typography variant="body2" sx={{ color: "grey.700", mb: 1 }}>
        Możesz w każdej chwili usunąć swoje konto razem ze wszystkimi danymi.
      </Typography>
      <Typography variant="body2" sx={{ color: "grey.600", mb: 2 }}>
        Tej operacji nie da się cofnąć — Twoich rozwiązań i postępów nie da się
        później odzyskać.
      </Typography>

      <Button variant="outlined" color="error" onClick={openDialog}>
        Usuń konto
      </Button>

      <Dialog
        open={isDialogOpen}
        onClose={closeDialog}
        aria-labelledby="delete-account-title"
        aria-describedby="delete-account-description"
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle id="delete-account-title">Usunąć konto na zawsze?</DialogTitle>
        <DialogContent>
          <DialogContentText id="delete-account-description" component="div">
            <Typography variant="body2" sx={{ mb: 1.5 }}>
              Tej operacji <strong>nie da się cofnąć</strong>. Usuniemy na zawsze:
            </Typography>
            <Box component="ul" sx={{ pl: 3, m: 0, mb: 2 }}>
              <Typography component="li" variant="body2">
                Twoje konto
              </Typography>
              <Typography component="li" variant="body2">
                wszystkie przesłane przez Ciebie rozwiązania
              </Typography>
              <Typography component="li" variant="body2">
                wszystkie oceny i komentarze od AI
              </Typography>
              <Typography component="li" variant="body2">
                wszystkie zdjęcia Twoich rozwiązań
              </Typography>
              <Typography component="li" variant="body2">
                całą historię Twoich postępów
              </Typography>
            </Box>
            <Typography variant="body2" sx={{ mb: 2 }}>
              Jeśli na pewno chcesz usunąć konto, wpisz poniżej{" "}
              <strong>{confirmationPhrase}</strong>.
            </Typography>
          </DialogContentText>

          <TextField
            fullWidth
            autoFocus
            id="delete-account-confirmation"
            label={`Wpisz ${confirmationPhrase}`}
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            disabled={isDeleting}
            slotProps={{
              htmlInput: {
                autoCapitalize: "characters",
                autoComplete: "off",
                spellCheck: false,
              },
            }}
          />

          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={closeDialog} disabled={isDeleting}>
            Anuluj
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={handleDelete}
            disabled={!isPhraseValid || isDeleting}
            startIcon={isDeleting ? <CircularProgress size={16} color="inherit" /> : undefined}
          >
            {isDeleting ? "Usuwanie..." : "Usuń konto na zawsze"}
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
