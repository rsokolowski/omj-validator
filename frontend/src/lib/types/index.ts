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
  content: string;
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
  year: string;
  etap: string;
  task_number: number;
  timestamp: string;
  status: "pending" | "processing" | "completed" | "failed";
  images: string[];
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
  year: string;
  etap: string;
  task_number: number;
  timestamp: string;
  status: "pending" | "processing" | "completed" | "failed";
  images: string[];
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
  year: string;
  etap: string;
  task_number: number;
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
}

export interface UserSubmissionsResponse {
  submissions: UserSubmissionListItem[];
  stats: UserSubmissionStats;
  total_count: number;
  offset: number;
  limit: number;
  has_more: boolean;
}
