import { readApiError } from "./errors";
import type { JobSummary } from "../types";

export interface AppSettings {
  onboarding_completed: boolean;
  data_dir: string;
  models_dir: string;
  logs_dir: string;
  asr_backend: string;
  mlx_whisper_model: string;
  mlx_whisper_model_dir: string;
  mlx_whisper_word_timestamps: boolean;
  whisperkit_executable_path: string;
  whisperkit_executable_ready: boolean;
  whisperkit_cli_workdir: string;
  whisperkit_model: string;
  whisperkit_model_path: string;
  whisperkit_model_ready: boolean;
  whisperkit_host: string;
  whisperkit_startup_timeout_seconds: number;
  whisperkit_request_timeout_seconds: number;
  asr_max_subtitle_chars: number;
  asr_max_subtitle_duration_ms: number;
  asr_min_subtitle_duration_ms: number;
  asr_max_word_gap_ms: number;
  whisper_executable_path: string;
  whisper_model_path: string;
  whisper_timestamp_precision: string;
  whisper_dtw_preset: string;
  provider_base_url: string;
  provider_model: string;
  provider_api_key_configured: boolean;
  provider_api_key_storage: "keychain" | "environment" | "none";
  provider_timeout_seconds: number;
  translation_batch_size: number;
  ytdlp_executable: string;
  ytdlp_cookies_configured: boolean;
}

export interface AppSettingsUpdate {
  provider_base_url?: string;
  provider_model?: string;
  provider_api_key?: string;
  clear_provider_api_key?: boolean;
  whisperkit_executable_path?: string;
  whisperkit_model?: string;
  whisperkit_model_path?: string;
  onboarding_completed?: boolean;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  checks: {
    ffmpeg: boolean;
    ffprobe: boolean;
    ytdlp: boolean;
    asr: Record<string, boolean | string>;
    translation_provider: boolean;
  };
}

let apiBaseUrlPromise: Promise<string> | null = null;
let cachedApiBaseUrl = "";

async function loadApiBaseUrl(): Promise<string> {
  const windowWithTauri = window as Window & { __TAURI_INTERNALS__?: unknown };
  if (!windowWithTauri.__TAURI_INTERNALS__) {
    return "";
  }
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const baseUrl = await invoke<string>("backend_base_url");
    cachedApiBaseUrl = baseUrl.replace(/\/$/, "");
    return cachedApiBaseUrl;
  } catch {
    return "";
  }
}

async function getApiBaseUrl(): Promise<string> {
  apiBaseUrlPromise ??= loadApiBaseUrl();
  return apiBaseUrlPromise;
}

function apiUrl(path: string, baseUrl = cachedApiBaseUrl): string {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  return `${baseUrl}${path}`;
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const baseUrl = await getApiBaseUrl();
  const url = apiUrl(path, baseUrl);
  const isSafeMethod = !init?.method || init.method === "GET" || init.method === "HEAD";
  const attempts = isSafeMethod ? 60 : 1;
  let lastError: unknown;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await fetch(url, init);
    } catch (error) {
      lastError = error;
      if (attempt === attempts) {
        break;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
  }

  throw lastError instanceof Error ? lastError : new Error("Failed to connect to backend");
}

export async function fetchHealth(): Promise<HealthResponse> {
  const response = await apiFetch("/api/health");
  if (!response.ok) {
    throw new Error("Failed to load health status");
  }
  return response.json();
}

export async function fetchJobs(): Promise<JobSummary[]> {
  const response = await apiFetch("/api/jobs");
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to load jobs"));
  }
  return response.json();
}

export async function fetchSettings(): Promise<AppSettings> {
  const response = await apiFetch("/api/settings");
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to load settings"));
  }
  return response.json();
}

export async function updateSettings(
  payload: AppSettingsUpdate,
): Promise<AppSettings> {
  const response = await apiFetch("/api/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to update settings"));
  }
  return response.json();
}

export async function testProviderSettings(payload: {
  base_url: string;
  model: string;
  api_key: string;
}): Promise<void> {
  const response = await apiFetch("/api/settings/provider/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Provider connection failed"));
  }
}

export async function createVideoFromUrlJob(formData: FormData): Promise<JobSummary> {
  const response = await apiFetch("/api/jobs/video-from-url", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to create URL video job"));
  }
  return response.json();
}

export async function createVideoJob(formData: FormData): Promise<JobSummary> {
  const response = await apiFetch("/api/jobs/video", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to create video job"));
  }
  return response.json();
}

export async function createSrtJob(formData: FormData): Promise<JobSummary> {
  const response = await apiFetch("/api/jobs/srt", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to create SRT job"));
  }
  return response.json();
}

export async function runJob(jobId: string): Promise<JobSummary> {
  const response = await apiFetch(`/api/jobs/${jobId}/run`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to start job"));
  }
  return response.json();
}

export async function translateJob(jobId: string): Promise<JobSummary> {
  const response = await apiFetch(`/api/jobs/${jobId}/translate`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to retry translation"));
  }
  return response.json();
}

export async function cancelJob(jobId: string): Promise<JobSummary> {
  const response = await apiFetch(`/api/jobs/${jobId}/cancel`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to cancel job"));
  }
  return response.json();
}

export async function deleteJob(jobId: string): Promise<void> {
  const response = await apiFetch(`/api/jobs/${jobId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to delete job"));
  }
}

export async function renameJob(jobId: string, filename: string): Promise<JobSummary> {
  const response = await apiFetch(`/api/jobs/${jobId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename }),
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to rename job"));
  }
  return response.json();
}

export async function openJobFolder(jobId: string): Promise<void> {
  const response = await apiFetch(`/api/jobs/${jobId}/open-folder`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await readApiError(response, "Failed to open output folder"));
  }
}

export function outputDownloadUrl(jobId: string, outputKey: string): string {
  return apiUrl(`/api/jobs/${jobId}/outputs/${encodeURIComponent(outputKey)}/download`);
}

export function jobLogUrl(jobId: string, logName: "ytdlp" | "whisperkit"): string {
  return apiUrl(`/api/jobs/${jobId}/logs/${logName}`);
}
