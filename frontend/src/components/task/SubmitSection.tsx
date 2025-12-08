"use client";

import { useState, useRef, DragEvent } from "react";
import { Paper, Typography, Box, Button, Alert, LinearProgress } from "@mui/material";
import { uploadFiles } from "@/lib/api/client";
import { SubmitResponse } from "@/lib/types";
import { getMaxScore } from "@/lib/utils/constants";

interface SubmitSectionProps {
  year: string;
  etap: string;
  num: number;
  canSubmit: boolean;
  isAuthenticated: boolean;
}

interface UploadState {
  status: "idle" | "uploading" | "success" | "error";
  progress: number;
  message?: string;
  result?: {
    score: number;
    max_score: number;
    feedback: string;
  };
}

export function SubmitSection({ year, etap, num, canSubmit, isAuthenticated }: SubmitSectionProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploadState, setUploadState] = useState<UploadState>({ status: "idle", progress: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      addFiles(Array.from(e.target.files));
    }
  };

  const addFiles = (newFiles: File[]) => {
    // Filter to only image files
    const imageFiles = newFiles.filter(file => file.type.startsWith("image/"));
    setFiles(prev => [...prev, ...imageFiles]);
    setUploadState({ status: "idle", progress: 0 });
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

    setUploadState({ status: "uploading", progress: 10 });

    try {
      // Simulate progress during upload
      const progressInterval = setInterval(() => {
        setUploadState((prev) => ({
          ...prev,
          progress: Math.min(prev.progress + 5, 90),
        }));
      }, 500);

      const result = await uploadFiles<SubmitResponse>(
        `/api/task/${year}/${etap}/${num}/submit`,
        files
      );

      clearInterval(progressInterval);

      const maxScore = getMaxScore(etap);
      setUploadState({
        status: "success",
        progress: 100,
        result: {
          score: result.score,
          max_score: maxScore,
          feedback: result.feedback,
        },
      });

      setFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (error) {
      setUploadState({
        status: "error",
        progress: 0,
        message: error instanceof Error ? error.message : "Wystąpił błąd podczas przesyłania",
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
    return (
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}>
          Prześlij rozwiązanie
        </Typography>
        <Alert severity="info">
          <Typography variant="body2">
            Zaloguj się, aby przesłać swoje rozwiązanie.{" "}
            <a href="/login" style={{ color: "inherit", fontWeight: 600 }}>
              Zaloguj się
            </a>
          </Typography>
        </Alert>
      </Paper>
    );
  }

  if (!canSubmit) {
    return (
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}>
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

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" sx={{ color: "grey.700", mb: 2, pb: 1.5, borderBottom: 1, borderColor: "grey.200" }}>
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
          cursor: "pointer",
          transition: "all 0.2s ease",
          "&:hover": {
            borderColor: "primary.main",
            bgcolor: "grey.100",
          },
        }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={handleFileSelect}
          style={{ display: "none" }}
        />
        <Typography variant="body1" sx={{ color: isDragging ? "primary.main" : "grey.600", mb: 0.5 }}>
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
              <Button size="small" color="error" onClick={() => handleRemoveFile(index)}>
                Usuń
              </Button>
            </Box>
          ))}
        </Box>
      )}

      {/* Upload Progress */}
      {uploadState.status === "uploading" && (
        <Box sx={{ mb: 2 }}>
          <LinearProgress variant="determinate" value={uploadState.progress} sx={{ mb: 1 }} />
          <Typography variant="body2" sx={{ color: "grey.600", textAlign: "center" }}>
            Analizowanie rozwiązania... ({uploadState.progress}%)
          </Typography>
        </Box>
      )}

      {/* Result */}
      {uploadState.status === "success" && uploadState.result && (
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
      {uploadState.status === "error" && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {uploadState.message}
        </Alert>
      )}

      {/* Submit Button */}
      <Button
        variant="contained"
        fullWidth
        disabled={files.length === 0 || uploadState.status === "uploading"}
        onClick={handleSubmit}
        sx={{ py: 1.5 }}
      >
        {uploadState.status === "uploading" ? "Przesyłanie..." : "Prześlij rozwiązanie"}
      </Button>
    </Paper>
  );
}
