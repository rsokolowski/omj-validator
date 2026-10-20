// Patterns (Wzorce) API - thin wrappers over fetchAPI
import { fetchAPI } from "./client";
import {
  ExerciseBatch,
  ExerciseGroup,
  Pattern,
  PatternDetail,
  PatternDraft,
  PatternLink,
  PatternQueue,
  PatternSource,
  PatternSuggestion,
  PracticeTask,
  RefineRound,
} from "@/lib/types";

export interface CreatePatternInput {
  trigger: string;
  action: string;
  example?: string;
  category?: string | null;
  skills?: string[];
  origin: "own" | "ai_suggested";
  source?: PatternSource | null;
  refinement: RefineRound[];
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const patternsApi = {
  refine: (body: {
    draft: PatternDraft;
    source?: PatternSource | null;
    history?: RefineRound[];
    answers?: (string | null)[];
    message?: string | null;
    category?: string | null;
    pattern_id?: string;
  }) =>
    // off_topic: the message was not about maths / the pattern - a decline in
    // `reply`, no round (it does not count as a refinement)
    fetchAPI<{ round?: RefineRound; off_topic?: boolean; reply?: string }>(
      "/api/patterns/refine",
      json("POST", body)
    ),

  suggest: (submissionId: string, draft?: string) =>
    fetchAPI<{ suggestions: PatternSuggestion[] }>(
      "/api/patterns/suggest",
      json("POST", { submission_id: submissionId, draft: draft || null })
    ),

  create: (input: CreatePatternInput) =>
    fetchAPI<{ pattern: PatternDetail }>("/api/patterns", json("POST", input)),

  get: (id: string) => fetchAPI<{ pattern: PatternDetail }>(`/api/patterns/${encodeURIComponent(id)}`),

  update: (id: string, body: Record<string, unknown>) =>
    fetchAPI<{ pattern: PatternDetail }>(`/api/patterns/${encodeURIComponent(id)}`, json("PATCH", body)),

  remove: (id: string) => fetchAPI<{ success: boolean }>(`/api/patterns/${encodeURIComponent(id)}`, json("DELETE")),

  forTask: (source: PatternSource) => {
    const query = source.task_key
      ? `task_key=${encodeURIComponent(source.task_key)}`
      : `private_task_id=${encodeURIComponent(source.private_task_id ?? "")}`;
    return fetchAPI<{ patterns: Pattern[] }>(`/api/patterns?${query}`);
  },

  queue: (limit = 10) => fetchAPI<PatternQueue>(`/api/patterns/queue?limit=${limit}`),

  suggestLinks: (id: string) =>
    fetchAPI<{ links: PatternLink[] }>(`/api/patterns/${encodeURIComponent(id)}/suggest-links`, json("POST")),

  addLink: (id: string, source: PatternSource) =>
    fetchAPI<{ link: PatternLink }>(`/api/patterns/${encodeURIComponent(id)}/links`, json("POST", source)),

  setLinkStatus: (id: string, linkId: number, status: "accepted" | "rejected") =>
    fetchAPI<{ link: PatternLink }>(
      `/api/patterns/${encodeURIComponent(id)}/links/${linkId}`,
      json("PATCH", { status })
    ),

  removeLink: (id: string, linkId: number) =>
    fetchAPI<{ success: boolean }>(`/api/patterns/${encodeURIComponent(id)}/links/${linkId}`, json("DELETE")),

  review: (id: string, recallText: string, outcome: "fail" | "hard" | "ok") =>
    fetchAPI<{ pattern: Pattern }>(
      `/api/patterns/${encodeURIComponent(id)}/review`,
      json("POST", { recall_text: recallText, outcome })
    ),

  practice: (id: string) =>
    fetchAPI<{ task: PracticeTask | null }>(`/api/patterns/${encodeURIComponent(id)}/practice`),

  generateExercises: (id: string) =>
    fetchAPI<{ batch: ExerciseBatch }>(`/api/patterns/${encodeURIComponent(id)}/exercises`, json("POST")),

  exerciseGroups: () => fetchAPI<{ groups: ExerciseGroup[] }>("/api/patterns/exercises"),

  activeExerciseBatches: () => fetchAPI<{ batches: ExerciseBatch[] }>("/api/patterns/exercise-batches/active"),

  acknowledgeExerciseBatch: (batchId: string) =>
    fetchAPI<{ success: boolean }>(
      `/api/patterns/exercise-batches/${encodeURIComponent(batchId)}/ack`,
      json("POST")
    ),
};

export function emptyDraft(): PatternDraft {
  return { trigger: "", action: "", example: "", raw: "" };
}
