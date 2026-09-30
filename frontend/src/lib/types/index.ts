// TypeScript types matching FastAPI Pydantic models

export interface User {
  google_sub: string;
  email: string;
  name: string;
  picture?: string;
  is_group_member: boolean;
}

export interface TaskPdf {
  tasks: string;
  solutions?: string;
  statistics?: string;
}

export interface TaskInfo {
  year: string;
  etap: string;
  number: number;
  title: string;
  content: string | null;
  has_content: boolean;
  pdf: TaskPdf;
  difficulty?: number;
  categories: string[];
  hints: string[];
  prerequisites: string[];
  skills_required: string[];
  skills_gained: string[];
}

export interface TaskWithStats extends TaskInfo {
  submission_count: number;
  highest_score: number | null;
}

export type TaskStatus = "locked" | "unlocked" | "mastered";

export interface SubmissionResult {
  success: boolean;
  submission_id: string;
  score: number;
  feedback: string;
}

export interface Submission {
  id: string;
  user_id: string;
  // OMJ task reference - null for a private task submission
  year: string | null;
  etap: string | null;
  task_number: number | null;
  private_task_id?: string | null;
  hints_used?: number;
  timestamp: string;
  status: "pending" | "processing" | "completed" | "failed";
  images: string[];
  solution_text?: string | null; // typed solution ($LaTeX$ text), null when photos only
  score: number | null;
  feedback: string | null;
  error_message?: string;
}

export interface SubmitResponse {
  success: boolean;
  submission_id: string;
  score: number;
  feedback: string;
}

export interface GraphNode {
  key: string;
  year: string;
  etap: string;
  number: number;
  title: string;
  difficulty?: number;
  categories: string[];
  prerequisites: string[];
  status: TaskStatus;
  best_score: number;
}

export interface GraphEdge {
  source: string;
  target: string;
}

export interface ProgressData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  recommendations: GraphNode[];
  stats: {
    total: number;
    mastered: number;
    unlocked: number;
    locked: number;
  };
}

export interface SkillInfo {
  id: string;
  name: string;
  category: string;
  description: string;
  examples: string[];
}

export interface PrerequisiteStatus {
  key: string;
  year: string;
  etap: string;
  number: number;
  title: string;
  status: "mastered" | "in_progress" | null;
  url: string;
}

// API response types
export interface TaskDetailResponse {
  task: TaskInfo;
  stats: { submission_count: number; highest_score: number | null } | null;
  submissions: Submission[];
  pdf_links: { tasks?: string; solutions?: string };
  user: User | null;
  is_authenticated: boolean;
  can_submit: boolean;
  skills_required: SkillInfo[];
  skills_gained: SkillInfo[];
  prerequisite_statuses: PrerequisiteStatus[];
}

export interface YearsResponse {
  years: string[];
  user: User | null;
  is_authenticated: boolean;
}

export interface EtapsResponse {
  year: string;
  etaps: string[];
  user: User | null;
  is_authenticated: boolean;
}

export interface TasksResponse {
  year: string;
  etap: string;
  tasks: TaskWithStats[];
  user: User | null;
  is_authenticated: boolean;
}

// Admin types
export type IssueType = "none" | "wrong_task" | "injection";

export interface AdminSubmission {
  id: string;
  user_id: string;
  user_email: string | null;
  user_name: string | null;
  year: string | null;
  etap: string | null;
  task_number: number | null;
  private_task_id?: string | null;
  task_title?: string | null;
  timestamp: string;
  status: "pending" | "processing" | "completed" | "failed";
  images: string[];
  solution_text?: string | null;
  score: number | null;
  feedback: string | null;
  error_message?: string | null;
  issue_type: IssueType;
  abuse_score: number;
}

export interface AdminSubmissionsResponse {
  submissions: AdminSubmission[];
  total_count: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export interface AdminRerunResponse {
  success: boolean;
  submission_id: string;
  status: string;
}

export interface AdminUser {
  google_sub: string;
  email: string;
  name: string | null;
}

export interface AdminUsersSearchResponse {
  users: AdminUser[];
}

export interface AdminMeResponse {
  user: User | null;
  is_authenticated: boolean;
  is_admin: boolean;
}

// User submissions types (Moje rozwiązania)
export interface UserSubmissionStats {
  total_submissions: number;
  completed_count: number;
  failed_count: number;
  pending_count: number;
  avg_score: number | null;
  best_score: number | null;
  tasks_attempted: number;
  tasks_mastered: number;
}

export interface UserSubmissionListItem {
  id: string;
  year: string | null;
  etap: string | null;
  task_number: number | null;
  private_task_id?: string | null;
  task_title: string;
  task_categories: string[];
  timestamp: string;
  status: "pending" | "processing" | "completed" | "failed";
  score: number | null;
  max_score: number;
  feedback: string | null;
  feedback_preview: string | null;
  error_message?: string | null;
  images: string[];
  solution_text?: string | null;
}

export interface UserSubmissionsResponse {
  submissions: UserSubmissionListItem[];
  stats: UserSubmissionStats;
  total_count: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

// Account deletion (RODO art. 17)
export interface AccountDeleteResponse {
  success: boolean;
  deleted_submissions: number;
  deleted_files: number;
}

// Private tasks (Moje zadania)
export type PrivateTaskOrigin = "photo" | "typed";

export interface PrivateTask {
  id: string;
  title: string;
  content: string;
  source_label: string | null;
  category: string | null;
  difficulty: number | null;
  origin: PrivateTaskOrigin;
  source_images: string[];
  hints_count: number;
  revealed_hints: string[];
  created_at: string;
  last_activity_at: string;
}

export interface PrivateTaskSummary {
  id: string;
  title: string;
  source_label: string | null;
  category: string | null;
  difficulty: number | null;
  origin: PrivateTaskOrigin;
  best_score: number | null;
  attempts: number;
  last_activity_at: string;
}

export interface PrivateTaskListResponse {
  tasks: PrivateTaskSummary[];
  total_count: number;
  offset: number;
  limit: number;
  has_more: boolean;
}

export interface PrivateTaskDetailResponse {
  task: PrivateTask;
  submissions: Submission[];
  stats: { submission_count: number; highest_score: number | null };
}

export interface ExtractedProblem {
  label: string;
  title: string;
  content: string;
  category: string | null;
  difficulty: number | null;
}

export interface ExtractResponse {
  draft_id: string;
  problems: ExtractedProblem[];
  photos: string[];
}

export interface PrivateTaskInput {
  title: string;
  content: string;
  source_label?: string | null;
  category?: string | null;
  difficulty?: number | null;
}

export interface CreatePrivateTasksResponse {
  tasks: PrivateTask[];
}

export interface RevealHintResponse {
  n: number;
  hint: string;
  hints_revealed: number;
}

// Patterns ("Wzorce")
export interface PatternVariant {
  trigger: string;
  action: string;
  example: string;
}

export interface PatternDraft {
  trigger: string;
  action: string;
  example: string;
  raw: string;
}

export type PatternVerdict = "ok" | "za_ogolny" | "bledny" | "to_nie_wzorzec";

/** A version offered in a refine round: how broad it is and OMJ tasks where it helps */
export interface RoundVariant extends PatternVariant {
  note?: string;
  tasks?: string[];
}

export interface RefineRound {
  draft: PatternDraft;
  /** Rounds saved before the conversation had separate fields: one answer for everything */
  answer?: string | null;
  /** The student's answers to the previous round's questions, same order */
  answers?: (string | null)[];
  /** The student's own message that requested this round */
  message?: string | null;
  /** The AI's direct reply to that message; OMJ tasks appear as [[2015_etap3_1]] */
  reply?: string;
  variants: RoundVariant[];
  questions: string[];
  verdict: PatternVerdict;
  comment: string;
  category?: string | null;
  skills?: string[];
  chosen: number | null;
  at?: string;
}

export interface PatternSuggestion extends PatternVariant {
  why: string;
  category?: string | null;
}

/** A suggestion handed from a task page to the new-pattern form */
export interface PatternInitialDraft extends PatternVariant {
  category?: string | null;
}

export interface PatternSource {
  task_key?: string;
  private_task_id?: string;
}

export interface PatternLink {
  id: number;
  role: "source" | "practice";
  origin: "ai" | "manual";
  status: "suggested" | "accepted" | "rejected";
  reason: string | null;
  task_key: string | null;
  private_task_id: string | null;
  kind: "omj" | "private";
  title: string;
  label?: string;
  url: string | null;
  difficulty?: number | null;
  available: boolean;
}

export interface PatternReview {
  id: number;
  kind: "recall" | "task";
  outcome: "fail" | "hard" | "ok";
  recall_text: string | null;
  submission_id: string | null;
  level_before: number;
  level_after: number;
  due_after: string;
  created_at: string;
}

export interface Pattern {
  id: string;
  trigger: string;
  action: string;
  example: string | null;
  category: string | null;
  skills: string[];
  origin: "own" | "ai_suggested";
  level: number;
  streak: number;
  due_on: string;
  is_due: boolean;
  review_count: number;
  lapse_count: number;
  archived: boolean;
  created_at: string;
  last_reviewed_at: string | null;
  links_count: number;
  suggested_links_count: number;
}

export interface PatternDetail extends Pattern {
  links: PatternLink[];
  refinement: RefineRound[];
  reviews: PatternReview[];
}

export interface PatternQueue {
  items: Pattern[];
  due_total: number;
}

export interface PracticeTask {
  kind: "omj" | "private";
  ref: string;
  title: string;
  url: string;
}
