// TypeScript types matching FastAPI Pydantic models

export interface User {
  id: string;
  /** null for login/password accounts (children without an e-mail) */
  email: string | null;
  /** null for Google accounts */
  login?: string | null;
  name: string;
  picture?: string | null;
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
  id: string;
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

// Admin: AI provider/model switch (GET/PUT /api/admin/ai-config)
export type AiProviderId = "gemini" | "anthropic";

export interface AiActiveModel {
  provider: AiProviderId;
  model: string;
  /** Catalog label, or the raw id when the server's env model is outside the catalog */
  model_label: string;
  /** "db" = chosen in /admin/settings, "env" = server configuration default */
  source: "db" | "env";
  updated_at: string | null;
  updated_by: string | null;
}

export interface AiModelOption {
  id: string;
  label: string;
}

export interface AiProviderOption {
  id: AiProviderId;
  label: string;
  /** API key is set on the server */
  configured: boolean;
  /** GDPR: student data may be sent to this provider */
  approved: boolean;
  models: AiModelOption[];
}

/** The model AI calls actually use right now */
export interface AiEffectiveModel {
  provider: AiProviderId;
  model: string;
  model_label: string;
}

export interface AiConfigResponse {
  /** The stored choice (or the server default) */
  active: AiActiveModel;
  /** What grades - differs from `active` when the stored choice is unusable */
  effective: AiEffectiveModel;
  /** Why `effective` differs from `active`, else null */
  fallback_reason: string | null;
  providers: AiProviderOption[];
}

export interface AiConfigUpdateResponse {
  active: AiActiveModel;
  effective: AiEffectiveModel;
  fallback_reason: string | null;
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

// Accounts: age step, parent consent, login/password accounts
export type AccountStatus = "active" | "pending_parent";
export type LoginMethod = "google" | "login";

/** Present while the account waits for a parent's consent */
export interface PendingInfo {
  /** Masked, e.g. "m***@example.com" */
  parent_email: string;
  /** When the account is deleted without consent (ISO, UTC) */
  deadline: string | null;
  /** Newest consent e-mail; null = nothing has gone out yet */
  last_sent_at: string | null;
  resend_available_at: string | null;
}

export interface AccountInfo {
  status: AccountStatus;
  /** No year of birth yet (account created before the age step) */
  needs_profile: boolean;
  login_method: LoginMethod;
  pending: PendingInfo | null;
}

export interface AuthMeResponse {
  user: User | null;
  account: AccountInfo | null;
  is_authenticated: boolean;
  is_admin: boolean;
  can_delete_account?: boolean;
  account_delete_confirmation?: string;
}

export interface RedirectResponse {
  redirect: string;
  email_sent?: boolean | null;
}

export type GoogleRegistrationResponse =
  | { action: "google"; redirect: string }
  | { action: "done"; redirect: string; email_sent: boolean | null };

export interface RegistrationStateResponse {
  google: { email: string } | null;
}

export interface LoginAvailableResponse {
  login: string;
  valid: boolean;
  available: boolean;
  message: string | null;
}

export interface ResendResponse {
  sent: true;
  account?: AccountInfo;
}

/** State of a link from an e-mail */
export type LinkState = "valid" | "expired" | "used" | "invalid";

/** A child's account as a parent sees it */
export interface ParentChild {
  id: string;
  kind: LoginMethod;
  /** "Login dziecka" / "Konto Google dziecka" */
  identifier_label: string;
  identifier: string;
  created_at: string;
  status: AccountStatus;
  pending_deadline: string | null;
}

export interface ProcessingSummary {
  /** e.g. "24 miesiące" */
  submission_retention: string;
  /** e.g. "36 miesięcy" */
  inactive_retention: string;
  pending_days: number;
}

export interface ConsentView {
  state: LinkState;
  child: ParentChild | null;
  can_resend: boolean;
  summary: ProcessingSummary;
}

export type ConsentDecisionResponse =
  | { result: "accepted"; manage_url: string; child: ParentChild }
  | { result: "declined" };

export interface ParentChildrenResponse {
  parent_email: string;
  children: ParentChild[];
}

export interface ParentDeleteResponse {
  deleted: true;
  remaining: number;
}

export interface PasswordResetCheckResponse {
  state: LinkState;
  login: string | null;
}
