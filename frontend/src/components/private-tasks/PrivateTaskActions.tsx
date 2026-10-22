"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from "@mui/material";
import { fetchAPI } from "@/lib/api/client";
import { PrivateTask } from "@/lib/types";
import { EditableTask, ProblemEditor, toInput, validateTask } from "./ProblemEditor";

function toEditable(task: PrivateTask): EditableTask {
  return {
    title: task.title,
    content: task.content,
    source_label: task.source_label ?? "",
    category: task.category ?? "",
    difficulty: task.difficulty ? String(task.difficulty) : "",
  };
}

export function PrivateTaskActions({ task }: { task: PrivateTask }) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [value, setValue] = useState<EditableTask>(toEditable(task));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Wystąpił błąd.");
    } finally {
      setBusy(false);
    }
  };

  const saveEdit = () => {
    const problem = validateTask(value);
    if (problem) {
      setError(problem);
      return;
    }
    const input = toInput(value);
    run(async () => {
      await fetchAPI(`/api/private-tasks/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify({ ...input, source_label: input.source_label ?? "" }),
      });
      setEditing(false);
      router.refresh();
    });
  };

  const regenerate = () =>
    run(async () => {
      await fetchAPI(`/api/private-tasks/${task.id}/regenerate-hints`, { method: "POST" });
      setNotice("Przygotowano nowe wskazówki.");
      router.refresh();
    });

  const remove = () =>
    run(async () => {
      await fetchAPI(`/api/private-tasks/${task.id}`, { method: "DELETE" });
      router.push("/moje-zadania");
      router.refresh();
    });

  return (
    <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", alignItems: "center" }}>
      <Button size="small" variant="outlined" onClick={() => { setValue(toEditable(task)); setEditing(true); }}>
        Edytuj
      </Button>
      <Button size="small" variant="outlined" onClick={regenerate} disabled={busy}>
        {task.hints_count ? "Nowe wskazówki" : "Wygeneruj wskazówki"}
      </Button>
      <Button size="small" color="error" onClick={() => setDeleting(true)}>
        Usuń
      </Button>
      {error && !editing && !deleting && (
        <Alert severity="error" sx={{ width: "100%" }}>
          {error}
        </Alert>
      )}
      {notice && !error && (
        <Alert severity="success" sx={{ width: "100%" }} onClose={() => setNotice(null)}>
          {notice}
        </Alert>
      )}

      <Dialog open={editing} onClose={() => !busy && setEditing(false)} fullWidth maxWidth="md">
        <DialogTitle>Edytuj zadanie</DialogTitle>
        <DialogContent>
          <DialogContentText sx={{ mb: 2 }}>
            Poprawiona treść będzie używana przy kolejnych ocenach. Wcześniejsze wyniki zostają
            ocenione według treści, która obowiązywała wtedy.
          </DialogContentText>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <ProblemEditor idPrefix="edit" value={value} onChange={setValue} disabled={busy} allowAuto={false} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditing(false)} disabled={busy}>
            Anuluj
          </Button>
          <Button variant="contained" onClick={saveEdit} disabled={busy}>
            Zapisz
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={deleting} onClose={() => !busy && setDeleting(false)}>
        <DialogTitle>Usunąć zadanie?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Zadanie, jego zdjęcia i wszystkie Twoje rozwiązania tego zadania zostaną trwale usunięte.
          </DialogContentText>
          {error && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleting(false)} disabled={busy}>
            Anuluj
          </Button>
          <Button color="error" variant="contained" onClick={remove} disabled={busy}>
            Usuń na zawsze
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
