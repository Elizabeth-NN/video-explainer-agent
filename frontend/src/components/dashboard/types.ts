export type GenerationSettings = {
  topic: string;
  model: "standard" | "gemini";
  voice: string;
  format: "landscape" | "vertical";
};

export type JobStatus = "queued" | "running" | "completed" | "failed";

export type GenerationJob = {
  job_id: string;
  topic: string;
  status: JobStatus;
  logs: string[];
  error: string | null;
};

export type RecentVideo = {
  job_id: string;
  topic: string;
  videoUrl: string;
};
