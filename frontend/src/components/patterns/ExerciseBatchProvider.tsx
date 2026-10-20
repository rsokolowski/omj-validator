"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import { Alert, Box, Button, Snackbar } from "@mui/material";
import { MathContent } from "@/components/ui/MathContent";
import { useAuth } from "@/lib/hooks/useAuth";
import { patternsApi } from "@/lib/api/patterns";
import { ExerciseBatch } from "@/lib/types";

const POLL_MS = 4000;
const ACTIVE_KEY = "/api/patterns/exercise-batches/active";

interface ExerciseBatchContextValue {
  /** Batches generating right now */
  running: ExerciseBatch[];
  /** Start watching a batch this tab just started (polling begins at once) */
  track: (batch: ExerciseBatch | null | undefined) => void;
}

const ExerciseBatchContext = createContext<ExerciseBatchContextValue>({ running: [], track: () => undefined });

export function useExerciseBatches() {
  return useContext(ExerciseBatchContext);
}

/** "1 ćwiczenie", "3 ćwiczenia", "5 ćwiczeń", "22 ćwiczenia" */
export function exercisesCount(n: number): string {
  if (n === 1) return "1 ćwiczenie";
  const few = n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 12 || n % 100 > 14);
  return `${n} ${few ? "ćwiczenia" : "ćwiczeń"}`;
}

/** Popup copy for a finished batch (the trigger may hold $LaTeX$) */
function PopupText({ batch }: { batch: ExerciseBatch }) {
  if (batch.status !== "done") return <>Nie udało się ułożyć ćwiczeń. Spróbuj ponownie na stronie wzorca.</>;
  return (
    <Box component="span" sx={{ "& .math-content": { display: "inline" } }}>
      Gotowe: {exercisesCount(batch.created_count)} do wzorca „<MathContent content={batch.trigger ?? ""} />”
    </Box>
  );
}

/**
 * Watches exercise generation running in the background: the header shows a
 * spinner while one runs and a popup appears on any page when it finishes.
 * Polls only while something runs; a finished batch is acknowledged when its
 * popup is shown, so it is not shown again in another tab or after a reload.
 */
export function ExerciseBatchProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated, isGroupMember } = useAuth();
  const enabled = isAuthenticated && isGroupMember;
  const [tracked, setTracked] = useState<ExerciseBatch[]>([]);
  const [queue, setQueue] = useState<ExerciseBatch[]>([]);
  const [dismissed, setDismissed] = useState<string | null>(null);
  const seen = useRef<Set<string>>(new Set());

  const onSuccess = useCallback(
    ({ batches }: { batches: ExerciseBatch[] }) => {
      // The server's answer replaces what this tab tracked (a batch another
      // tab already acknowledged is simply gone from it)
      setTracked((t) => (t.length ? [] : t));
      const finished = batches.filter((b) => b.status !== "running" && !seen.current.has(b.id));
      if (!finished.length) return;
      finished.forEach((b) => {
        seen.current.add(b.id);
        patternsApi.acknowledgeExerciseBatch(b.id).catch(() => undefined);
      });
      setQueue((q) => [...q, ...finished]);
      // Server-rendered lists (wzorzec page, Moje zadania) pick up the new exercises
      router.refresh();
    },
    [router]
  );

  // Once on sign-in (resumes a batch started before a reload, shows a missed
  // popup), then every few seconds while something is running
  const { data, mutate } = useSWR(enabled ? ACTIVE_KEY : null, () => patternsApi.activeExerciseBatches(), {
    refreshInterval: (latest) =>
      latest?.batches.some((b) => b.status === "running") || tracked.length ? POLL_MS : 0,
    revalidateOnFocus: true,
    shouldRetryOnError: false,
    onSuccess,
  });

  const fetched = (data?.batches ?? []).filter((b) => b.status === "running");
  const running = [...fetched, ...tracked.filter((t) => !fetched.some((b) => b.id === t.id))];

  const track = useCallback(
    (batch: ExerciseBatch | null | undefined) => {
      if (batch?.status !== "running") return;
      setTracked((t) => (t.some((b) => b.id === batch.id) ? t : [...t, batch]));
      mutate();
    },
    [mutate]
  );

  const current = queue[0];
  const close = (_?: unknown, reason?: string) => {
    if (reason === "clickaway" || !current) return;
    setDismissed(current.id);
  };

  return (
    <ExerciseBatchContext.Provider value={{ running, track }}>
      {children}
      <Snackbar
        key={current?.id}
        open={!!current && dismissed !== current.id}
        autoHideDuration={10000}
        onClose={close}
        TransitionProps={{ onExited: () => setQueue((q) => q.slice(1)) }}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
      >
        {current ? (
          <Alert
            severity={current.status === "done" ? "success" : "error"}
            variant="filled"
            onClose={close}
            action={
              <Button
                color="inherit"
                size="small"
                onClick={() => {
                  close();
                  router.push(`/wzorce/${current.pattern_id}`);
                }}
              >
                {current.status === "done" ? "Zobacz" : "Otwórz"}
              </Button>
            }
            sx={{ alignItems: "center" }}
          >
            <PopupText batch={current} />
          </Alert>
        ) : (
          <span />
        )}
      </Snackbar>
    </ExerciseBatchContext.Provider>
  );
}
