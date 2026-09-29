"use client";

import { useState, useRef, DragEvent, useEffect, useCallback, useId } from "react";
import { useRouter } from "next/navigation";
import {
  Paper,
  Typography,
  Box,
  Button,
  Alert,
  CircularProgress,
  IconButton,
} from "@mui/material";
import BrushIcon from "@mui/icons-material/Brush";
import CloseIcon from "@mui/icons-material/Close";
import { uploadFiles } from "@/lib/api/client";
import { MAX_UPLOAD_FILES, SUBMISSION_TEXT_MAX_CHARS, getMaxScore } from "@/lib/utils/constants";
import { countChars, formatCount, normalizeSolutionText } from "@/lib/utils/solutionText";
import { LoginPrompt } from "@/components/common/LoginPrompt";
import { MathContent } from "@/components/ui/MathContent";
import { AiGeneratedNotice } from "@/components/ui/AiGeneratedNotice";
import { DrawingDialog } from "./DrawingDialog";
import { SolutionTextEditor } from "./SolutionTextEditor";

interface SubmitSectionProps {
  year?: string;
  etap?: string;
  num?: number;
  canSubmit: boolean;
  isAuthenticated: boolean;
  /** Endpoint to POST photos and/or text to - defaults to the OMJ task's submit route */
  submitUrl?: string;
  /** Page to return to after login - defaults to the OMJ task page */
  pagePath?: string;
  /** Called after a graded result arrives (default: refresh the page) */
  onCompleted?: () => void;
  /** Submission already sent from another page ("Odczytaj zadanie i oceń") -
   *  follow its grading from the moment this section mounts */
  resumeSubmissionId?: string;
}

interface SubmitResponse {
  success: boolean;
  submission_id: string;
  status: string;
  message: string;
  ws_path: string;
}

type SubmitStatus = "idle" | "processing" | "completed" | "failed";

/** A chosen photo or drawing with the object URL of its thumbnail */
interface SelectedFile {
  file: File;
  url: string;
}

/**
 * Technika "visually hidden": element zostaje w drzewie dostepnosci
 * (inaczej niz przy `display: none`, ktore usuwa go takze z kolejnosci
 * tabulacji), ale nie jest widoczny. Tylko przez `style`, nie `sx`: w sx
 * width/height 1 oznacza 100%.
 */
const visuallyHidden = {
  position: "absolute",
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: "hidden",
  clip: "rect(0 0 0 0)",
  whiteSpace: "nowrap",
  border: 0,
} as const;

interface UploadState {
  status: SubmitStatus;
  statusMessage: string;
  result?: {
    score: number;
    max_score: number;
    feedback: string;
  };
  error?: string;
}

// WebSocket message types
interface StatusMessage {
  type: "status";
  submission_id: string;
  message: string;
}

interface CompletedMessage {
  type: "completed";
  submission_id: string;
  score: number;
  feedback: string;
}

interface ErrorMessage {
  type: "error";
  submission_id: string;
  error: string;
}

type WebSocketMessage = StatusMessage | CompletedMessage | ErrorMessage;

export function SubmitSection({
  year,
  etap,
  num,
  canSubmit,
  isAuthenticated,
  submitUrl,
  pagePath,
  onCompleted,
  resumeSubmissionId,
}: SubmitSectionProps) {
  const router = useRouter();
  const [files, setFiles] = useState<SelectedFile[]>([]);
  // Thumbnail URLs still to revoke on clear/unmount - kept current after each render
  const filesRef = useRef<SelectedFile[]>([]);
  // "pominięto n" after the list hit MAX_UPLOAD_FILES
  const [filesNotice, setFilesNotice] = useState("");
  const [solutionText, setSolutionText] = useState("");
  const [drawingOpen, setDrawingOpen] = useState(false);
  // Numbers drawings within this visit: rysunek-1.png, rysunek-2.png, ...
  const drawingCounterRef = useRef(0);
  const normalizedText = normalizeSolutionText(solutionText);
  const textCount = countChars(normalizedText);
  const textTooLong = textCount > SUBMISSION_TEXT_MAX_CHARS;
  const hasSomething = files.length > 0 || normalizedText.length > 0;
  const helperId = useId();
  const [uploadState, setUploadState] = useState<UploadState>({
    status: "idle",
    statusMessage: "",
  });
  const [isDragging, setIsDragging] = useState(false);
  // Komunikat dla czytnika ekranu. Celowo NIE jest to `statusMessage`:
  // backend przysyla nowy status przy kazdej zmianie naglowka w strumieniu
  // rozumowania modelu, a ogloszenie kazdego z nich zamienia region zywy
  // w halas. Ogłaszamy wylacznie zmiany fazy (WCAG 4.1.3).
  const [liveMessage, setLiveMessage] = useState("");
  const announcedAnalysisRef = useRef(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  // Release the thumbnails when the page goes away
  useEffect(() => {
    return () => filesRef.current.forEach((f) => URL.revokeObjectURL(f.url));
  }, []);

  const clearFiles = useCallback(() => {
    filesRef.current.forEach((f) => URL.revokeObjectURL(f.url));
    filesRef.current = [];
    setFiles([]);
    setFilesNotice("");
  }, []);

  // A new photo, drawing or text edit starts a new attempt: the previous
  // result or error is cleared (never while a submission is being graded)
  const resetOutcome = () =>
    setUploadState((prev) =>
      prev.status === "processing" || prev.status === "idle" ? prev : { status: "idle", statusMessage: "" }
    );

  const connectWebSocket = useCallback(
    (wsPath: string) => {
      // Determine WebSocket URL
      // In production, use NEXT_PUBLIC_WS_URL env var pointing to backend
      // In development, connect directly to backend on localhost:8000
      let wsUrl: string;
      if (process.env.NEXT_PUBLIC_WS_URL) {
        // Production: use configured WebSocket URL
        wsUrl = `${process.env.NEXT_PUBLIC_WS_URL}${wsPath}`;
      } else if (process.env.NODE_ENV === "development") {
        // Development: connect directly to backend
        wsUrl = `ws://localhost:8000${wsPath}`;
      } else {
        // Fallback: try same host (works if backend serves frontend)
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        wsUrl = `${protocol}//${window.location.host}${wsPath}`;
      }

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("[WebSocket] Connected:", wsPath);
      };

      ws.onmessage = (event) => {
        try {
          const msg: WebSocketMessage = JSON.parse(event.data);
          console.log("[WebSocket] Message:", msg.type, msg);

          switch (msg.type) {
            case "status":
              if (!announcedAnalysisRef.current) {
                announcedAnalysisRef.current = true;
                setLiveMessage(
                  "Rozwiązanie zostało przesłane. Trwa ocenianie, może to potrwać kilkanaście sekund."
                );
              }
              setUploadState((prev) => ({
                ...prev,
                statusMessage: msg.message,
              }));
              break;

            case "completed":
              // Wynik oglasza <Alert role="alert"> - nie dublujemy go tutaj.
              setLiveMessage("");
              const maxScore = getMaxScore(etap ?? null);
              setUploadState({
                status: "completed",
                statusMessage: "",
                result: {
                  score: msg.score,
                  max_score: maxScore,
                  feedback: msg.feedback,
                },
              });
              clearFiles();
              setSolutionText("");
              if (fileInputRef.current) {
                fileInputRef.current.value = "";
              }
              ws.close();
              // Refresh the page to update submission history
              if (onCompleted) {
                onCompleted();
              } else {
                router.refresh();
              }
              break;

            case "error":
              // Blad oglasza <Alert severity="error"> (role="alert").
              setLiveMessage("");
              setUploadState({
                status: "failed",
                statusMessage: "",
                error: msg.error,
              });
              ws.close();
              break;
          }
        } catch (e) {
          console.error("[WebSocket] Failed to parse message:", e);
        }
      };

      ws.onerror = (error) => {
        console.error("[WebSocket] Error:", error);
      };

      ws.onclose = () => {
        console.log("[WebSocket] Closed");
        wsRef.current = null;
      };
    },
    [etap, router, onCompleted, clearFiles]
  );

  useEffect(() => {
    if (!resumeSubmissionId) return;
    // Drop ?ocena= from the address: the result is delivered to the first
    // WebSocket only, so after a reload the history below shows it instead
    window.history.replaceState(null, "", window.location.pathname);
    announcedAnalysisRef.current = true;
    setUploadState({ status: "processing", statusMessage: "Oceniam rozwiązanie..." });
    setLiveMessage("Rozwiązanie zostało przesłane. Trwa ocenianie, może to potrwać do minuty.");
    connectWebSocket(`/ws/submissions/${encodeURIComponent(resumeSubmissionId)}`);
  }, [resumeSubmissionId, connectWebSocket]);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      addFiles(Array.from(e.target.files));
    }
  };

  const addFiles = (newFiles: File[]) => {
    const imageFiles = newFiles.filter((file) => file.type.startsWith("image/"));
    const kept = imageFiles.slice(0, Math.max(0, MAX_UPLOAD_FILES - files.length));
    const dropped = imageFiles.length - kept.length;
    setFiles([...files, ...kept.map((file) => ({ file, url: URL.createObjectURL(file) }))]);
    setFilesNotice(
      dropped > 0 ? `Można dodać najwyżej ${MAX_UPLOAD_FILES} zdjęć i rysunków – pominięto ${dropped}.` : ""
    );
    resetOutcome();
  };

  const addDrawing = (png: Blob) => {
    drawingCounterRef.current += 1;
    addFiles([new File([png], `rysunek-${drawingCounterRef.current}.png`, { type: "image/png" })]);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files) {
      addFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleRemoveFile = (index: number) => {
    URL.revokeObjectURL(files[index].url);
    setFiles(files.filter((_, i) => i !== index));
    setFilesNotice("");
  };

  const handleSubmit = async () => {
    if (!hasSomething || textTooLong) return;

    // Reset state
    announcedAnalysisRef.current = false;
    setUploadState({
      status: "processing",
      statusMessage: "Przesyłanie rozwiązania...",
    });
    setLiveMessage("Przesyłanie rozwiązania. Proszę czekać.");

    try {
      // Step 1: Upload files via POST
      const result = await uploadFiles<SubmitResponse>(
        submitUrl ?? `/api/task/${year}/${etap}/${num}/submit`,
        files.map((f) => f.file),
        undefined,
        normalizedText ? { solution_text: solutionText } : undefined
      );

      if (!result.success || !result.submission_id) {
        throw new Error("Nie udało się przesłać rozwiązania");
      }

      // Step 2: Connect WebSocket for progress
      connectWebSocket(result.ws_path);
    } catch (error) {
      setLiveMessage("");
      setUploadState({
        status: "failed",
        statusMessage: "",
        error: error instanceof Error ? error.message : "Wystąpił błąd podczas przesyłania",
      });
    }
  };

  const getScoreColor = (score: number, maxScore: number) => {
    const ratio = score / maxScore;
    if (ratio >= 0.8) return "success";
    if (ratio >= 0.4) return "warning";
    return "error";
  };

  if (!isAuthenticated) {
    const currentUrl = pagePath ?? `/task/${year}/${etap}/${num}`;
    return (
      <LoginPrompt
        title="Prześlij rozwiązanie"
        message="Zaloguj się, aby przesłać swoje rozwiązanie"
        redirectUrl={currentUrl}
      />
    );
  }

  if (!canSubmit) {
    return (
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography
          variant="h6"
          component="h2"
          sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}
        >
          Prześlij rozwiązanie
        </Typography>
        <Alert severity="warning">
          <Typography variant="body2">
            Nie masz uprawnień do przesyłania rozwiązań. Skontaktuj się z administratorem.
          </Typography>
        </Alert>
      </Paper>
    );
  }

  const isProcessing = uploadState.status === "processing";
  const hasResult = uploadState.status === "completed" && Boolean(uploadState.result);
  const canSend = hasSomething && !textTooLong && !isProcessing;
  const helper = !hasSomething
    ? "Prześlij zdjęcia, rysunek albo wpisz rozwiązanie."
    : textTooLong
      ? `Skróć tekst do ${formatCount(SUBMISSION_TEXT_MAX_CHARS)} znaków.`
      : null;

  // Jedno oznaczenie AI na sekcję: przy wyniku, jeśli wynik jest widoczny,
  // w przeciwnym razie tuż pod nagłówkiem (uprzedza, kto oceni rozwiązanie).
  const aiNotice = <AiGeneratedNotice variant="evaluation" style={{ marginBottom: "16px" }} />;

  return (
    <Paper sx={{ p: 3, mb: 3 }} aria-busy={isProcessing}>
      <Typography
        variant="h6"
        component="h2"
        sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}
      >
        Prześlij rozwiązanie
      </Typography>

      {/* Region zywy dla przebiegu oceniania (WCAG 4.1.3). Jest w DOM zawsze,
          takze gdy nic sie nie dzieje - region dodany do drzewa razem z
          trescia bywa przez czytniki pomijany. Wynik i blad maja wlasny
          role="alert" w <Alert>, wiec ich tu nie powtarzamy. */}
      <Box role="status" aria-live="polite" aria-atomic="true" style={visuallyHidden}>
        {liveMessage}
      </Box>

      {!hasResult && aiNotice}

      {/* Wybor plikow.
          Glowna droga to prawdziwy przycisk-etykieta: dziala z klawiatury,
          ma nazwe dostepna i widoczny pierscien fokusu (WCAG 2.1.1, 3.3.2,
          4.1.2). Pole <input type="file"> jest ukryte technika "visually
          hidden", a nie `display: none`, ktore usuwalo je z kolejnosci
          tabulacji. Przeciaganie i upuszczanie zostaje jako udogodnienie dla
          myszy - nie jest jedynym sposobem dzialania, wiec obszar nie
          potrzebuje wlasnej roli ani obslugi klawiatury. */}
      <Box
        sx={{
          mb: 2,
          p: 3,
          border: 2,
          borderStyle: "dashed",
          // grey.500 zamiast grey.300: 4,63:1 wobec tla grey.50 (WCAG 1.4.11)
          borderColor: isDragging ? "primary.main" : "grey.500",
          borderRadius: 2,
          bgcolor: isDragging ? "primary.50" : "grey.50",
          textAlign: "center",
          transition: "all 0.2s ease",
          opacity: isProcessing ? 0.6 : 1,
        }}
        onDragOver={isProcessing ? undefined : handleDragOver}
        onDragLeave={isProcessing ? undefined : handleDragLeave}
        onDrop={isProcessing ? undefined : handleDrop}
      >
        <Typography
          variant="body1"
          sx={{ color: isDragging ? "primary.main" : "grey.700", mb: 1.5 }}
        >
          {isDragging
            ? "Upuść zdjęcia tutaj"
            : "Przeciągnij tutaj zdjęcia rozwiązania albo wybierz je przyciskiem poniżej."}
        </Typography>
        {/* `role={undefined}` i `tabIndex={-1}`: gdyby etykieta udawala przycisk
            (domyslne role="button" z MUI), ButtonBase przechwytywalby Enter
            i wywolywal wylacznie reactowy onClick - natywne "klikniecie w
            etykiete otwiera wybor pliku" nigdy by nie zadzialalo (sprawdzone
            w przegladarce). Fokusowalne jest wiec samo pole pliku: to jeden
            przystanek tabulacji, ktory reaguje na Enter i na spacje. */}
        <Box sx={{ display: "flex", gap: 1, justifyContent: "center", flexWrap: "wrap" }}>
          <Button
            component="label"
            role={undefined}
            tabIndex={-1}
            variant="outlined"
            disabled={isProcessing}
            sx={{
              // Fokus trafia na ukryte pole, wiec pierscien fokusu musi pokazac
              // przycisk (WCAG 2.4.7).
              "&:has(input:focus-visible)": {
                outline: "3px solid",
                outlineColor: "primary.main",
                outlineOffset: "2px",
              },
            }}
          >
            Wybierz zdjęcia rozwiązania
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              onChange={handleFileSelect}
              disabled={isProcessing}
              style={visuallyHidden}
            />
          </Button>
          <Button
            variant="outlined"
            startIcon={<BrushIcon />}
            onClick={() => setDrawingOpen(true)}
            disabled={isProcessing || files.length >= MAX_UPLOAD_FILES}
          >
            Dodaj rysunek
          </Button>
        </Box>
        <Typography variant="caption" component="p" sx={{ color: "grey.600", mt: 1.5 }}>
          Akceptowane formaty: JPG, PNG, HEIC
        </Typography>
      </Box>

      {/* Selected Files */}
      <Typography variant="body2" sx={{ color: "grey.700", mb: files.length ? 1 : 2 }}>
        Zdjęcia i rysunki: {files.length} / {MAX_UPLOAD_FILES}
      </Typography>
      {/* Always in the DOM, so screen readers announce the notice when it appears */}
      <Typography role="status" variant="body2" sx={{ color: "warning.dark", mb: filesNotice ? 1 : 0 }}>
        {filesNotice}
      </Typography>
      {files.length > 0 && (
        <Box component="ul" sx={{ display: "flex", flexWrap: "wrap", gap: 1, listStyle: "none", p: 0, m: 0, mb: 2 }}>
          {files.map(({ file, url }, index) => (
            <Box
              component="li"
              key={url}
              data-testid="image-preview"
              sx={{
                position: "relative",
                width: 96,
                height: 96,
                border: 1,
                borderColor: "grey.300",
                borderRadius: 1,
                overflow: "hidden",
                bgcolor: "grey.100",
              }}
            >
              {/* Decorative: the name below says what it is. A format the browser
                  cannot show (HEIC) leaves the grey box with the name. */}
              <Box
                component="img"
                src={url}
                alt=""
                onError={(e) => {
                  e.currentTarget.style.visibility = "hidden";
                }}
                sx={{ width: "100%", height: "100%", objectFit: "contain", bgcolor: "common.white" }}
              />
              <Typography
                variant="caption"
                component="span"
                title={file.name}
                sx={{
                  position: "absolute",
                  left: 0,
                  right: 0,
                  bottom: 0,
                  px: 0.5,
                  fontSize: 10,
                  color: "common.white",
                  bgcolor: "rgba(0,0,0,.6)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {file.name}
              </Typography>
              <IconButton
                size="small"
                onClick={() => handleRemoveFile(index)}
                disabled={isProcessing}
                aria-label={`Usuń ${file.name}`}
                sx={{
                  position: "absolute",
                  top: 2,
                  right: 2,
                  p: 0.25,
                  color: "common.white",
                  bgcolor: "rgba(0,0,0,.6)",
                  "&:hover": { bgcolor: "rgba(0,0,0,.8)" },
                  "&.Mui-focusVisible": { outline: "3px solid", outlineColor: "primary.main" },
                }}
              >
                <CloseIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Box>
          ))}
        </Box>
      )}

      <Typography variant="subtitle1" component="h3" sx={{ color: "grey.800", mt: 1 }}>
        Albo wpisz rozwiązanie
      </Typography>
      <Typography variant="body2" sx={{ color: "grey.600", mb: 1.5 }}>
        Możesz połączyć tekst ze zdjęciami lub rysunkami – np. opisać rozumowanie i dołączyć szkic.
      </Typography>
      <Box sx={{ mb: 2 }}>
        <SolutionTextEditor
          value={solutionText}
          onChange={(next) => {
            setSolutionText(next);
            resetOutcome();
          }}
          maxChars={SUBMISSION_TEXT_MAX_CHARS}
          disabled={isProcessing}
        />
      </Box>

      {/* Processing Status */}
      {isProcessing && (
        <Box
          sx={{
            mb: 2,
            p: 2,
            bgcolor: "grey.50",
            borderRadius: 1,
            display: "flex",
            alignItems: "center",
            gap: 2,
          }}
        >
          <CircularProgress size={24} />
          <Box>
            <Typography variant="body2" sx={{ color: "grey.700" }}>
              {uploadState.statusMessage || "Przetwarzanie..."}
            </Typography>
            <Typography variant="caption" component="p" sx={{ color: "grey.600" }}>
              Ocena trwa zwykle do minuty, przy trudniejszych rozwiązaniach dłużej.
            </Typography>
          </Box>
        </Box>
      )}

      {/* Result */}
      {hasResult && uploadState.result && (
        <>
          {aiNotice}
          <Alert
            severity={getScoreColor(uploadState.result.score, uploadState.result.max_score)}
            sx={{ mb: 2 }}
          >
            <Typography variant="subtitle2" component="p" sx={{ fontWeight: 600, mb: 1 }}>
              Wynik: {uploadState.result.score} / {uploadState.result.max_score} punktów
            </Typography>
            <Box sx={{ "& .math-content": { fontSize: "0.875rem" } }}>
              <MathContent content={uploadState.result.feedback} />
            </Box>
          </Alert>
        </>
      )}

      {/* Error */}
      {uploadState.status === "failed" && uploadState.error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {uploadState.error}
        </Alert>
      )}

      {/* Submit Button */}
      <Button
        variant="contained"
        fullWidth
        disabled={!canSend}
        aria-describedby={helper && !isProcessing ? helperId : undefined}
        onClick={handleSubmit}
        sx={{ py: 1.5 }}
      >
        {isProcessing ? "Przetwarzanie..." : "Prześlij rozwiązanie"}
      </Button>
      {helper && !isProcessing && (
        <Typography
          id={helperId}
          variant="caption"
          component="p"
          sx={{ color: "grey.600", mt: 1, textAlign: "center" }}
        >
          {helper}
        </Typography>
      )}

      <DrawingDialog open={drawingOpen} onClose={() => setDrawingOpen(false)} onAdd={addDrawing} />
    </Paper>
  );
}
