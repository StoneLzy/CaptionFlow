export type StageName =
  | "upload"
  | "download"
  | "track_mux"
  | "transcription"
  | "merge"
  | "translation"
  | "export";
export type StageStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type JobStatus = "created" | "running" | "completed" | "failed" | "cancelled";

export interface StageProgress {
  name: StageName;
  status: StageStatus;
  detail: string;
  percent?: number | null;
  processed?: number | null;
  total?: number | null;
  elapsed_seconds?: number | null;
}

export interface JobSummary {
  id: string;
  filename: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
  progress: StageProgress[];
  error_summary?: string | null;
  outputs: Record<string, string>;
}
