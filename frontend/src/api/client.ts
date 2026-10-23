export type Preset = "best" | "1080" | "720" | "480" | "audio";
export const PRESETS: Preset[] = ["best", "1080", "720", "480", "audio"];

export type JobStatus = "queued" | "downloading" | "processing" | "expanded" | "done" | "failed";

export interface PlaylistEntry {
  url: string;
  title: string | null;
  duration: number | null;
}

export interface MediaInfo {
  kind: "single" | "playlist";
  url: string;
  title: string | null;
  thumbnail: string | null;
  duration: number | null;
  uploader: string | null;
  presets: Preset[];
  count: number | null;
  entries: PlaylistEntry[];
}

export interface Progress {
  stage: "downloading" | "processing";
  percent: number | null;
  speed: number | null;
  eta: number | null;
  downloaded: number | null;
  total: number | null;
}

export interface FileInfo {
  name: string;
  size: number;
}

export interface Job {
  id: string;
  batch_id: string;
  url: string;
  status: JobStatus;
  parent_id: string | null;
  title: string | null;
  engine: string | null;
  progress: Progress | null;
  files: FileInfo[];
  error: { code: string; message: string } | null;
  expires_at: string;
}

export interface Batch {
  id: string;
  preset: Preset;
  created_at: string;
  expires_at: string;
}

export interface BatchState {
  batch: Batch;
  jobs: Job[];
}

export interface BatchCreated {
  batch_id: string;
  jobs: number;
  truncated: boolean;
}

export interface Limits {
  max_batch_urls: number;
  max_playlist_items: number;
}

export const DEFAULT_LIMITS: Limits = { max_batch_urls: 50, max_playlist_items: 50 };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}) },
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiError(0, "OFFLINE", String(error));
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    if (detail && typeof detail === "object" && "code" in detail) {
      const { code, message } = detail as { code: string; message: string };
      throw new ApiError(response.status, code, message);
    }
    throw new ApiError(response.status, "UNKNOWN", `HTTP ${response.status}`);
  }
  return body as T;
}

export const api = {
  probe: (url: string, signal?: AbortSignal) =>
    request<MediaInfo>("/api/probe", { method: "POST", body: JSON.stringify({ url }), signal }),
  createBatch: (urls: string[], preset: Preset) =>
    request<BatchCreated>("/api/batches", { method: "POST", body: JSON.stringify({ urls, preset }) }),
  batch: (id: string) => request<BatchState>(`/api/batches/${id}`),
  limits: () => request<Limits>("/api/limits"),
  eventsUrl: (id: string) => `/api/batches/${id}/events`,
  fileUrl: (jobId: string, index: number) => `/api/files/${jobId}?i=${index}`,
  zipUrl: (batchId: string) => `/api/batches/${batchId}/zip`,
};
