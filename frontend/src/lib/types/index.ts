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
