"use client";

import dynamic from "next/dynamic";
import { useRef, useState } from "react";
import {
  Alert,
  Button,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import { EditorLoadBoundary } from "./EditorLoadBoundary";
import type { DrawingHandle } from "./ExcalidrawCanvas";

// Excalidraw is loaded the first time the dialog opens, never on the server.
// EXCALIDRAW_ASSET_PATH must be set before the module evaluates: its font URLs
// are "<asset path>fonts/<Family>/<file>" and the copy lives in public/excalidraw/.
const ExcalidrawCanvas = dynamic(
  async () => {
    (window as unknown as { EXCALIDRAW_ASSET_PATH?: string }).EXCALIDRAW_ASSET_PATH = "/excalidraw/";
    const mod = await import("./ExcalidrawCanvas");
    return mod.ExcalidrawCanvas;
  },
  { ssr: false, loading: () => <CircularProgress size={24} aria-label="Ładowanie edytora rysunków" /> }
);

export interface DrawingDialogProps {
  open: boolean;
  onClose: () => void;
  /** Called with the exported PNG; the dialog closes and its scene is discarded */
  onAdd: (png: Blob) => void;
}

/**
 * A drawing is not re-editable once added (the student removes it from the
 * list and draws again) - that keeps scene state out of SubmitSection.
 */
export function DrawingDialog({ open, onClose, onAdd }: DrawingDialogProps) {
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down("sm"));
  const handleRef = useRef<DrawingHandle | null>(null);
  const [empty, setEmpty] = useState(true);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const close = () => {
    handleRef.current = null;
    setEmpty(true);
    setConfirmDiscard(false);
    setError(null);
    onClose();
  };

  const requestClose = () => {
    if (handleRef.current && !handleRef.current.isEmpty()) {
      setConfirmDiscard(true);
      return;
    }
    close();
  };

  const add = async () => {
    const handle = handleRef.current;
    if (!handle || handle.isEmpty()) return;
    setExporting(true);
    setError(null);
    try {
      onAdd(await handle.toPng());
      close();
    } catch {
      setError("Nie udało się zapisać rysunku — spróbuj ponownie.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <>
      <Dialog
        open={open}
        onClose={requestClose}
        fullScreen={fullScreen}
        fullWidth
        maxWidth="lg"
        aria-labelledby="drawing-dialog-title"
        slotProps={{ paper: { sx: { height: fullScreen ? "100%" : "92vh" } } }}
      >
        <DialogTitle id="drawing-dialog-title">Rysunek do rozwiązania</DialogTitle>
        <DialogContent sx={{ p: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 1 }}>
              {error}
            </Alert>
          )}
          <div style={{ flex: 1, minHeight: 0, border: "1px solid #e0e0e0", borderRadius: 4, overflow: "hidden" }}>
            <EditorLoadBoundary>
              {open && (
                <ExcalidrawCanvas
                  onReady={(handle) => {
                    handleRef.current = handle;
                  }}
                  onEmptyChange={setEmpty}
                />
              )}
            </EditorLoadBoundary>
          </div>
        </DialogContent>
        <DialogActions sx={{ px: 2, gap: 1, flexWrap: "wrap" }}>
          {/* On a phone the note takes its own row instead of a narrow column */}
          <Typography variant="caption" sx={{ color: "grey.600", flex: 1, flexBasis: { xs: "100%", sm: 0 } }}>
            Rysunek zostanie dołączony jako obraz. Po dodaniu nie da się go edytować – można go
            usunąć i narysować od nowa.
          </Typography>
          <Button onClick={requestClose} disabled={exporting}>
            Anuluj
          </Button>
          <Button variant="contained" onClick={add} disabled={empty || exporting}>
            Dodaj do rozwiązania
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={confirmDiscard} onClose={() => setConfirmDiscard(false)}>
        <DialogTitle>Porzucić rysunek?</DialogTitle>
        <DialogContent>
          <DialogContentText>Rysunek nie został dodany do rozwiązania i zostanie utracony.</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmDiscard(false)}>Wróć do rysowania</Button>
          <Button color="error" onClick={close}>
            Porzuć
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
