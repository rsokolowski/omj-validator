"use client";

import { RefObject, useEffect, useRef, useState } from "react";
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

/** What the form is waiting for; each step is an AI or upload call */
type Phase = "extract" | "save" | "submit";

const PHASE_TEXT: Record<Phase, { title: string; detail: string }> = {
  extract: {
    title: "Odczytuję zadanie ze zdjęcia…",
    detail: "AI czyta zdjęcie i przepisuje treść. Zwykle trwa to do minuty - nie zamykaj tej strony.",
  },
  save: {
    title: "Zapisuję zadanie i przygotowuję wskazówki…",
    detail: "To zwykle kilka sekund.",
  },
  submit: {
    title: "Wysyłam rozwiązanie do oceny…",
    detail: "Za chwilę przejdziesz do zadania, gdzie zobaczysz ocenę.",
  },
};

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

function imagesOnly(list: FileList | null): File[] {
  return Array.from(list ?? [])
    .filter((f) => f.type.startsWith("image/"))
    .slice(0, MAX_UPLOAD_FILES);
}

function PhotoPicker({
  label,
  files,
  onChange,
  inputRef,
  disabled,
}: {
  label: string;
  files: File[];
  onChange: (files: File[]) => void;
  inputRef: RefObject<HTMLInputElement | null>;
  disabled: boolean;
}) {
  return (
    <Box sx={{ display: "flex", gap: 2, alignItems: "center", flexWrap: "wrap", mb: 2 }}>
      <Button
        component="label"
        role={undefined}
        tabIndex={-1}
        variant="outlined"
        disabled={disabled}
        sx={{
          "&:has(input:focus-visible)": {
            outline: "3px solid",
            outlineColor: "primary.main",
            outlineOffset: "2px",
          },
        }}
      >
        {label}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={(e) => onChange(imagesOnly(e.target.files))}
          disabled={disabled}
          style={visuallyHidden}
        />
      </Button>
      <Typography variant="body2" sx={{ color: "grey.600" }}>
        {files.length ? `Wybrano: ${files.map((f) => f.name).join(", ")}` : "Nie wybrano zdjęć"}
      </Typography>
    </Box>
  );
}

/** Visible wait notice with a running clock - extraction alone can take a minute.
 *  Keyed by phase, so the clock restarts with each step. */
function PhaseProgress({ phase, step }: { phase: Phase; step: string | null }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  const { title, detail } = PHASE_TEXT[phase];
  return (
    <Box sx={{ mb: 2, p: 2, bgcolor: "grey.50", borderRadius: 1, display: "flex", alignItems: "center", gap: 2 }}>
      <CircularProgress size={24} />
      <Box>
        <Typography variant="body2" sx={{ color: "grey.800", fontWeight: 600 }}>
          {step && `${step}: `}
          {title}
        </Typography>
        <Typography variant="body2" sx={{ color: "grey.700" }}>
          {detail}
        </Typography>
        {/* Decorative: the phase change is announced by the live region, not every second */}
        <Typography variant="caption" component="p" sx={{ color: "grey.600" }} aria-hidden="true">
          {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}
        </Typography>
      </Box>
    </Box>
  );
}

export function NewPrivateTaskForm() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("photo");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);
  const [phase, setPhase] = useState<Phase | null>(null);
  // Set while "Odczytaj zadanie i oceń" runs its three steps
  const [grading, setGrading] = useState(false);
  // A task saved by the grading flow whose solution upload then failed
  const [savedTaskId, setSavedTaskId] = useState<string | null>(null);

  // Photo flow
  const [files, setFiles] = useState<File[]>([]);
  const [extracting, setExtracting] = useState(false);
  const [draft, setDraft] = useState<ExtractResponse | null>(null);
  const [selected, setSelected] = useState<boolean[]>([]);
  const [edits, setEdits] = useState<EditableTask[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [solutionFiles, setSolutionFiles] = useState<File[]>([]);
  const solutionInputRef = useRef<HTMLInputElement>(null);

  // Typed flow
  const [typed, setTyped] = useState<EditableTask>(emptyTask());

  const busy = extracting || saving;

  const resetPhoto = () => {
    setDraft(null);
    setSelected([]);
    setEdits([]);
    setFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setSolutionFiles([]);
    if (solutionInputRef.current) solutionInputRef.current.value = "";
    setSavedTaskId(null);
  };

  const extract = async (grade: boolean) => {
    if (!files.length || (grade && !solutionFiles.length)) return;
    setExtracting(true);
    setGrading(grade);
    setPhase("extract");
    setError(null);
    setStatus("Odczytuję zadania ze zdjęcia. To może potrwać do minuty.");
    let found: EditableTask[] = [];
    let result: ExtractResponse;
    try {
      result = await uploadFiles<ExtractResponse>("/api/private-tasks/extract", files);
      found = result.problems.map((p) => ({
        title: p.title,
        content: p.content,
        source_label: "",
        category: p.category ?? "",
        difficulty: p.difficulty ? String(p.difficulty) : "",
      }));
      setDraft(result);
      // One problem: pre-select it. Several: let the student choose.
      setSelected(result.problems.map(() => result.problems.length === 1));
      setEdits(found);
    } catch (e) {
      setStatus("");
      setError(errorText(e, "Nie udało się odczytać zadania."));
      setPhase(null);
      setGrading(false);
      return;
    } finally {
      setExtracting(false);
    }

    // One clean problem and a solution: save and grade without stopping.
    // Anything else stops at the review below, as the plain button does.
    if (grade && found.length === 1 && !validateTask(found[0])) {
      await save(found, result.draft_id, true);
      return;
    }
    setPhase(null);
    setGrading(false);
    setStatus(
      found.length === 1
        ? grade
          ? "Odczytano jedno zadanie. Popraw treść i kliknij Zapisz i oceń."
          : "Odczytano jedno zadanie. Sprawdź treść i zapisz."
        : `Odczytano ${found.length} zadania. Zaznacz te, które chcesz zapisać.`
    );
  };

  const save = async (tasks: EditableTask[], draftId: string | null, grade = false) => {
    for (const [index, task] of tasks.entries()) {
      const problem = validateTask(task);
      if (problem) {
        setError(tasks.length > 1 ? `Zadanie ${index + 1}: ${problem}` : problem);
        return;
      }
    }
    setSaving(true);
    setGrading(grade);
    setPhase("save");
    setError(null);
    setStatus("Zapisuję i przygotowuję wskazówki…");
    let taskId: string;
    try {
      const result = await fetchAPI<CreatePrivateTasksResponse>("/api/private-tasks", {
        method: "POST",
        body: JSON.stringify({ draft_id: draftId, tasks: tasks.map(toInput) }),
      });
      if (result.tasks.length !== 1 || !grade) {
        setStatus("Zapisano.");
        router.push(result.tasks.length === 1 ? `/moje-zadania/${result.tasks[0].id}` : "/moje-zadania");
        router.refresh();
        return;
      }
      taskId = result.tasks[0].id;
    } catch (e) {
      setStatus("");
      setError(errorText(e, "Nie udało się zapisać zadania."));
      setSaving(false);
      setPhase(null);
      setGrading(false);
      return;
    }

    setPhase("submit");
    setStatus("Zadanie zapisane. Wysyłam rozwiązanie do oceny.");
    try {
      const submitted = await uploadFiles<{ submission_id: string }>(
        `/api/private-tasks/${taskId}/submit`,
        solutionFiles
      );
      // The task page follows the grading over the WebSocket
      router.push(`/moje-zadania/${taskId}?ocena=${submitted.submission_id}`);
      router.refresh();
    } catch (e) {
      setStatus("");
      setError(
        `Nie udało się wysłać rozwiązania: ${errorText(e, "nieznany błąd")}.`
      );
      setSavedTaskId(taskId);
      setSaving(false);
      setPhase(null);
      setGrading(false);
    }
  };

  const chosen = draft ? edits.filter((_, i) => selected[i]) : [];
  const step = grading && phase ? `Krok ${{ extract: 1, save: 2, submit: 3 }[phase]} z 3` : null;

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

      {/* Outlives the error (switching tabs clears it): the task is saved and
          this is the way to it, since saving the draft again is disabled */}
      {savedTaskId && (
        <Alert
          severity="info"
          sx={{ mb: 2 }}
          action={
            <Button color="inherit" size="small" onClick={() => router.push(`/moje-zadania/${savedTaskId}`)}>
              Przejdź do zadania
            </Button>
          }
        >
          Zadanie jest zapisane - rozwiązanie prześlesz na jego stronie.
        </Alert>
      )}

      {phase && <PhaseProgress key={phase} phase={phase} step={step} />}

      {mode === "photo" && (
        <Box id="panel-photo" role="tabpanel" aria-labelledby="tab-photo">
          {!draft && (
            <>
              <Typography variant="body2" sx={{ color: "grey.700", mb: 2 }}>
                Zrób zdjęcie strony z zadaniem (np. z broszury albo zbioru). AI przepisze treść -
                zanim zapiszesz, sprawdzisz ją i poprawisz. Jeśli na zdjęciu jest kilka zadań,
                wybierzesz, które zapisać.
              </Typography>
              <PhotoPicker
                label="Wybierz zdjęcia zadania"
                files={files}
                onChange={(chosen) => {
                  setFiles(chosen);
                  setError(null);
                }}
                inputRef={fileInputRef}
                disabled={busy}
              />
              <Typography variant="body2" sx={{ color: "grey.700", mb: 2 }}>
                Masz już rozwiązanie? Dodaj też jego zdjęcia i kliknij „Odczytaj zadanie i oceń” -
                zadanie zostanie zapisane, a rozwiązanie od razu ocenione.
              </Typography>
              <PhotoPicker
                label="Wybierz zdjęcia rozwiązania"
                files={solutionFiles}
                onChange={(chosen) => {
                  setSolutionFiles(chosen);
                  setError(null);
                }}
                inputRef={solutionInputRef}
                disabled={busy}
              />
              <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
                <Button
                  variant={solutionFiles.length ? "outlined" : "contained"}
                  onClick={() => extract(false)}
                  disabled={!files.length || busy}
                >
                  Odczytaj zadanie
                </Button>
                <Button
                  variant="contained"
                  onClick={() => extract(true)}
                  disabled={!files.length || !solutionFiles.length || busy}
                >
                  Odczytaj zadanie i oceń
                </Button>
              </Box>
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
              {solutionFiles.length > 0 && chosen.length > 1 && (
                <Typography variant="body2" sx={{ color: "grey.700" }}>
                  Rozwiązanie można ocenić tylko dla jednego zadania - zaznacz jedno, żeby
                  zapisać je i ocenić.
                </Typography>
              )}
              <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
                {solutionFiles.length > 0 && !savedTaskId && (
                  <Button
                    variant="contained"
                    onClick={() => save(chosen, draft.draft_id, true)}
                    disabled={chosen.length !== 1 || busy}
                  >
                    Zapisz i oceń
                  </Button>
                )}
                <Button
                  variant={solutionFiles.length && !savedTaskId ? "outlined" : "contained"}
                  onClick={() => save(chosen, draft.draft_id)}
                  disabled={!chosen.length || busy || Boolean(savedTaskId)}
                >
                  {saving && !grading
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
