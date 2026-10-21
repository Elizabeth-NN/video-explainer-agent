export type VideoCategory = "cs" | "physics";

export type GenerationSettings = {
  topic: string;
  category: VideoCategory;
  model: "standard" | "gemini";
  voice: string;
  format: "landscape" | "vertical";
};

export type JobStatus = "queued" | "running" | "completed" | "failed";

export type GenerationJob = {
  job_id: string;
  topic: string;
  category: VideoCategory;
  status: JobStatus;
  logs: string[];
  error: string | null;
};

export type RecentVideo = {
  job_id: string;
  topic: string;
  category: VideoCategory;
  videoUrl: string;
};
