"use client";

import { useState, useRef, DragEvent, useEffect, useCallback } from "react";
import {
  Paper,
  Typography,
  Box,
  Button,
  Alert,
  CircularProgress,
} from "@mui/material";
import { uploadFiles } from "@/lib/api/client";
import { getMaxScore } from "@/lib/utils/constants";
import { LoginPrompt } from "@/components/common/LoginPrompt";

interface SubmitSectionProps {
  year: string;
  etap: string;
  num: number;
  canSubmit: boolean;
  isAuthenticated: boolean;
}

interface SubmitResponse {
  success: boolean;
  submission_id: string;
  status: string;
  message: string;
  ws_path: string;
}

type SubmitStatus = "idle" | "processing" | "completed" | "failed";

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
}: SubmitSectionProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploadState, setUploadState] = useState<UploadState>({
    status: "idle",
    statusMessage: "",
  });
  const [isDragging, setIsDragging] = useState(false);
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
              setUploadState((prev) => ({
                ...prev,
                statusMessage: msg.message,
              }));
              break;

            case "completed":
              const maxScore = getMaxScore(etap);
              setUploadState({
                status: "completed",
                statusMessage: "",
                result: {
                  score: msg.score,
                  max_score: maxScore,
                  feedback: msg.feedback,
                },
              });
              setFiles([]);
              if (fileInputRef.current) {
                fileInputRef.current.value = "";
              }
              ws.close();
              break;

            case "error":
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
    [etap]
  );

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      addFiles(Array.from(e.target.files));
    }
  };

  const addFiles = (newFiles: File[]) => {
    const imageFiles = newFiles.filter((file) => file.type.startsWith("image/"));
    setFiles((prev) => [...prev, ...imageFiles]);
    setUploadState({
      status: "idle",
      statusMessage: "",
    });
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
    setFiles(files.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    if (files.length === 0) return;

    // Reset state
    setUploadState({
      status: "processing",
      statusMessage: "Przesyłanie zdjęć...",
    });

    try {
      // Step 1: Upload files via POST
      const result = await uploadFiles<SubmitResponse>(
        `/api/task/${year}/${etap}/${num}/submit`,
        files
      );

      if (!result.success || !result.submission_id) {
        throw new Error("Nie udało się przesłać rozwiązania");
      }

      // Step 2: Connect WebSocket for progress
      connectWebSocket(result.ws_path);
    } catch (error) {
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
    const currentUrl = `/task/${year}/${etap}/${num}`;
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

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography
        variant="h6"
        sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}
      >
        Prześlij rozwiązanie
      </Typography>

      {/* Drag and Drop Zone */}
      <Box
        sx={{
          mb: 2,
          p: 3,
          border: 2,
          borderStyle: "dashed",
          borderColor: isDragging ? "primary.main" : "grey.300",
          borderRadius: 2,
          bgcolor: isDragging ? "primary.50" : "grey.50",
          textAlign: "center",
          cursor: isProcessing ? "not-allowed" : "pointer",
          transition: "all 0.2s ease",
          opacity: isProcessing ? 0.6 : 1,
          "&:hover": isProcessing
            ? {}
            : {
                borderColor: "primary.main",
                bgcolor: "grey.100",
              },
        }}
        onDragOver={isProcessing ? undefined : handleDragOver}
        onDragLeave={isProcessing ? undefined : handleDragLeave}
        onDrop={isProcessing ? undefined : handleDrop}
        onClick={isProcessing ? undefined : () => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFileSelect}
          style={{ display: "none" }}
          disabled={isProcessing}
        />
        <Typography
          variant="body1"
          sx={{ color: isDragging ? "primary.main" : "grey.600", mb: 0.5 }}
        >
          {isDragging ? "Upuść zdjęcia tutaj" : "Przeciągnij zdjęcia lub kliknij, aby wybrać"}
        </Typography>
        <Typography variant="caption" sx={{ color: "grey.500" }}>
          Akceptowane formaty: JPG, PNG
        </Typography>
      </Box>

      {/* Selected Files */}
      {files.length > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" sx={{ color: "grey.600", mb: 1 }}>
            Wybrano {files.length} {files.length === 1 ? "plik" : files.length < 5 ? "pliki" : "plików"}:
          </Typography>
          {files.map((file, index) => (
            <Box
              key={index}
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                p: 1,
                mb: 0.5,
                bgcolor: "grey.50",
                borderRadius: 1,
              }}
            >
              <Typography variant="body2" sx={{ color: "grey.700" }}>
                {file.name}
              </Typography>
              <Button
                size="small"
                color="error"
                onClick={() => handleRemoveFile(index)}
                disabled={isProcessing}
              >
                Usuń
              </Button>
            </Box>
          ))}
        </Box>
      )}

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
          <Typography variant="body2" sx={{ color: "grey.700" }}>
            {uploadState.statusMessage || "Przetwarzanie..."}
          </Typography>
        </Box>
      )}

      {/* Result */}
      {uploadState.status === "completed" && uploadState.result && (
        <Alert
          severity={getScoreColor(uploadState.result.score, uploadState.result.max_score)}
          sx={{ mb: 2 }}
        >
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
            Wynik: {uploadState.result.score} / {uploadState.result.max_score} punktów
          </Typography>
          <Typography variant="body2" sx={{ whiteSpace: "pre-wrap" }}>
            {uploadState.result.feedback}
          </Typography>
        </Alert>
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
        disabled={files.length === 0 || isProcessing}
        onClick={handleSubmit}
        sx={{ py: 1.5 }}
      >
        {isProcessing ? "Przetwarzanie..." : "Prześlij rozwiązanie"}
      </Button>
    </Paper>
  );
}
