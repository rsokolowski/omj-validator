"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  CircularProgress,
  FormControlLabel,
  Paper,
  Tab,
  Tabs,
  Typography,
} from "@mui/material";
import { fetchAPI, uploadFiles } from "@/lib/api/client";
import { CreatePrivateTasksResponse, ExtractResponse } from "@/lib/types";
import { MAX_UPLOAD_FILES } from "@/lib/utils/constants";
import { MathContent } from "@/components/ui/MathContent";
import { AiGeneratedNotice } from "@/components/ui/AiGeneratedNotice";
import { EditableTask, ProblemEditor, emptyTask, toInput, validateTask } from "./ProblemEditor";

type Mode = "photo" | "typed";

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

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

export function NewPrivateTaskForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("photo");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  // Photo flow
  const [files, setFiles] = useState<File[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [draft, setDraft] = useState<ExtractResponse | null>(null);
  const [selected, setSelected] = useState<boolean[]>([]);
  const [edits, setEdits] = useState<EditableTask[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Typed flow
  const [typed, setTyped] = useState<EditableTask>(emptyTask());

  const busy = extracting || saving;

  const resetPhoto = () => {
    setDraft(null);
    setSelected([]);
    setEdits([]);
    setFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const chosen = Array.from(e.target.files ?? []).filter((f) => f.type.startsWith("image/"));
    setFiles(chosen.slice(0, MAX_UPLOAD_FILES));
    setError(null);
  };

  const extract = async () => {
    if (!files.length) return;
    setExtracting(true);
    setError(null);
    setStatus("Odczytuję zadania ze zdjęcia. To może potrwać do minuty.");
    try {
      const result = await uploadFiles<ExtractResponse>("/api/private-tasks/extract", files);
      setDraft(result);
      // One problem: pre-select it. Several: let the student choose.
      setSelected(result.problems.map(() => result.problems.length === 1));
      setEdits(
        result.problems.map((p) => ({
          title: p.title,
          content: p.content,
          source_label: "",
          category: p.category ?? "",
          difficulty: p.difficulty ? String(p.difficulty) : "",
        }))
      );
      setStatus(
        result.problems.length === 1
          ? "Odczytano jedno zadanie. Sprawdź treść i zapisz."
          : `Odczytano ${result.problems.length} zadania. Zaznacz te, które chcesz zapisać.`
      );
    } catch (e) {
      setStatus("");
      setError(errorText(e, "Nie udało się odczytać zadania."));
    } finally {
      setExtracting(false);
    }
  };

  const save = async (tasks: EditableTask[], draftId: string | null) => {
    for (const [index, task] of tasks.entries()) {
      const problem = validateTask(task);
      if (problem) {
        setError(tasks.length > 1 ? `Zadanie ${index + 1}: ${problem}` : problem);
        return;
      }
    }
    setSaving(true);
    setError(null);
    setStatus("Zapisuję i przygotowuję wskazówki…");
    try {
      const result = await fetchAPI<CreatePrivateTasksResponse>("/api/private-tasks", {
        method: "POST",
        body: JSON.stringify({ draft_id: draftId, tasks: tasks.map(toInput) }),
      });
      setStatus("Zapisano.");
      if (result.tasks.length === 1) {
        router.push(`/moje-zadania/${result.tasks[0].id}`);
      } else {
        router.push("/moje-zadania");
      }
      router.refresh();
    } catch (e) {
      setStatus("");
      setError(errorText(e, "Nie udało się zapisać zadania."));
      setSaving(false);
    }
  };

  const chosen = draft ? edits.filter((_, i) => selected[i]) : [];

  return (
    <Paper sx={{ p: 3 }} aria-busy={busy}>
      <Box role="status" aria-live="polite" aria-atomic="true" sx={visuallyHidden}>
        {status}
      </Box>

      <Tabs
        value={mode}
        onChange={(_, value: Mode) => {
          setMode(value);
          setError(null);
        }}
        aria-label="Sposób dodania zadania"
        sx={{ mb: 3, borderBottom: 1, borderColor: "grey.200" }}
      >
        <Tab label="Ze zdjęcia" value="photo" id="tab-photo" aria-controls="panel-photo" disabled={busy} />
        <Tab label="Wpisz treść" value="typed" id="tab-typed" aria-controls="panel-typed" disabled={busy} />
      </Tabs>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {mode === "photo" && (
        <Box id="panel-photo" role="tabpanel" aria-labelledby="tab-photo">
          {!draft && (
            <>
              <Typography variant="body2" sx={{ color: "grey.700", mb: 2 }}>
                Zrób zdjęcie strony z zadaniem (np. z broszury albo zbioru). AI przepisze treść -
                zanim zapiszesz, sprawdzisz ją i poprawisz. Jeśli na zdjęciu jest kilka zadań,
                wybierzesz, które zapisać.
              </Typography>
              <Box sx={{ display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap", mb: 2 }}>
                <Button
                  component="label"
                  role={undefined}
                  tabIndex={-1}
                  variant="outlined"
                  disabled={busy}
                  sx={{
                    "&:has(input:focus-visible)": {
                      outline: "3px solid",
                      outlineColor: "primary.main",
                      outlineOffset: "2px",
                    },
                  }}
                >
                  Wybierz zdjęcia zadania
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={handleFiles}
                    disabled={busy}
                    style={visuallyHidden}
                  />
                </Button>
                <Typography variant="body2" sx={{ color: "grey.600" }}>
                  {files.length
                    ? `Wybrano: ${files.map((f) => f.name).join(", ")}`
                    : "Nie wybrano zdjęć"}
                </Typography>
              </Box>
              <Button variant="contained" onClick={extract} disabled={!files.length || busy}>
                {extracting ? (
                  <>
                    <CircularProgress size={18} sx={{ mr: 1, color: "inherit" }} /> Odczytuję…
                  </>
                ) : (
                  "Odczytaj zadanie"
                )}
              </Button>
            </>
          )}

          {draft && (
            <Box sx={{ display: "grid", gap: 3 }}>
              <AiGeneratedNotice variant="taskContent" />
              {draft.photos.length > 0 && (
                <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                  {draft.photos.map((photo, i) => (
                    <Box
                      key={photo}
                      component="img"
                      src={`/uploads/${photo}`}
                      alt={`Zdjęcie ${i + 1} z ${draft.photos.length}`}
                      sx={{ height: 96, borderRadius: 1, border: 1, borderColor: "grey.200" }}
                    />
                  ))}
                </Box>
              )}
              {draft.problems.map((problem, i) => (
                <Box
                  key={i}
                  sx={{
                    border: 1,
                    borderColor: selected[i] ? "primary.main" : "grey.300",
                    borderRadius: 2,
                    p: 2,
                  }}
                >
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={selected[i] ?? false}
                        onChange={(e) =>
                          setSelected((prev) => prev.map((v, j) => (j === i ? e.target.checked : v)))
                        }
                        disabled={busy}
                      />
                    }
                    label={
                      <Typography sx={{ fontWeight: 600 }}>
                        {problem.label}: {problem.title}
                      </Typography>
                    }
                  />
                  {selected[i] ? (
                    <Box sx={{ mt: 2 }}>
                      <ProblemEditor
                        idPrefix={`problem-${i}`}
                        value={edits[i]}
                        onChange={(value) => setEdits((prev) => prev.map((v, j) => (j === i ? value : v)))}
                        disabled={busy}
                      />
                    </Box>
                  ) : (
                    <Box sx={{ color: "grey.700", mt: 1, maxHeight: 120, overflow: "hidden" }}>
                      <MathContent content={problem.content} />
                    </Box>
                  )}
                </Box>
              ))}
              <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
                <Button
                  variant="contained"
                  onClick={() => save(chosen, draft.draft_id)}
                  disabled={!chosen.length || busy}
                >
                  {saving
                    ? "Zapisuję…"
                    : chosen.length > 1
                      ? `Zapisz zadania (${chosen.length})`
                      : "Zapisz zadanie"}
                </Button>
                <Button variant="text" onClick={resetPhoto} disabled={busy}>
                  Inne zdjęcie
                </Button>
              </Box>
            </Box>
          )}
        </Box>
      )}

      {mode === "typed" && (
        <Box id="panel-typed" role="tabpanel" aria-labelledby="tab-typed" sx={{ display: "grid", gap: 2 }}>
          <ProblemEditor idPrefix="typed" value={typed} onChange={setTyped} disabled={busy} />
          <Box>
            <Button variant="contained" onClick={() => save([typed], null)} disabled={busy}>
              {saving ? "Zapisuję…" : "Zapisz zadanie"}
            </Button>
          </Box>
        </Box>
      )}
    </Paper>
  );
}
