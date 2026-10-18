"use client";

import { useEffect, useState } from "react";
import {
  Bell,
  List,
  ArrowUpRight,
  CheckCircle,
  WarningCircle,
} from "@phosphor-icons/react";
import Sidebar from "./Sidebar";
import GenerationForm from "./GenerationForm";
import WorkflowProgress from "./WorkflowProgress";
import VideoPreview from "./VideoPreview";
import RecentVideos from "./RecentVideos";
import type {
  GenerationJob,
  GenerationSettings,
  RecentVideo,
} from "./types";

type ApiStatus = "checking" | "online" | "offline";
type Notice = { kind: "info" | "error"; text: string };

function getApiBase() {
  return (
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000"
  ).replace(/\/+$/, "");
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body.detail || `Request failed (${response.status}).`;
  } catch {
    return `Request failed (${response.status}).`;
  }
}

export default function DashboardClient() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [notice, setNotice] = useState<Notice | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [job, setJob] = useState<GenerationJob | null>(null);
  const [recentVideos, setRecentVideos] = useState<RecentVideo[]>([]);

  const busy =
    submitting || job?.status === "queued" || job?.status === "running";

  useEffect(() => {
    let active = true;

    async function checkApi() {
      try {
        const response = await fetch(`${getApiBase()}/api/health`, {
          cache: "no-store",
        });

        if (!response.ok) throw new Error("Health check failed");
        if (active) setApiStatus("online");
      } catch {
        if (active) setApiStatus("offline");
      }
    }

    void checkApi();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!activeJobId) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function pollJob() {
      try {
        const response = await fetch(
          `${getApiBase()}/api/jobs/${activeJobId}`,
          { cache: "no-store" },
        );

        if (!response.ok) {
          throw new Error(await readError(response));
        }

        const updatedJob: GenerationJob = await response.json();
        if (cancelled) return;

        setJob(updatedJob);

        if (updatedJob.status === "completed") {
          const videoUrl =
            `${getApiBase()}/api/jobs/${updatedJob.job_id}/video`;

          setRecentVideos((previous) => [
            {
              job_id: updatedJob.job_id,
              topic: updatedJob.topic,
              videoUrl,
            },
            ...previous.filter(
              (video) => video.job_id !== updatedJob.job_id,
            ),
          ]);

          setNotice({
            kind: "info",
            text: "Your video is ready to play or download.",
          });
          return;
        }

        if (updatedJob.status === "failed") {
          setNotice({
            kind: "error",
            text:
              updatedJob.error ||
              "Video generation failed. Check the workflow logs.",
          });
          return;
        }

        timer = setTimeout(() => void pollJob(), 2000);
      } catch (error) {
        if (cancelled) return;

        setNotice({
          kind: "error",
          text:
            error instanceof Error
              ? `Could not refresh job status: ${error.message}. Retrying…`
              : "Could not refresh job status. Retrying…",
        });

        timer = setTimeout(() => void pollJob(), 3000);
      }
    }

    void pollJob();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [activeJobId]);

  async function handleGenerate(settings: GenerationSettings) {
    if (busy) return;

    setSubmitting(true);
    setNotice(null);
    setJob(null);
    setActiveJobId(null);

    try {
      const response = await fetch(`${getApiBase()}/api/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: settings.topic,
          use_gemini: settings.model === "gemini",
          voice: settings.voice,
        }),
      });

      if (!response.ok) {
        throw new Error(await readError(response));
      }

      const createdJob: {
        job_id: string;
        topic: string;
        status: "queued";
      } = await response.json();

      setJob({
        ...createdJob,
        logs: [],
        error: null,
      });

      setActiveJobId(createdJob.job_id);
      setNotice({
        kind: "info",
        text: "Generation started. Your workflow logs will update as it runs.",
      });
    } catch (error) {
      setNotice({
        kind: "error",
        text:
          error instanceof Error
            ? `Could not start generation: ${error.message}`
            : "Could not start video generation.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  const currentVideo =
    job?.status === "completed"
      ? recentVideos.find((video) => video.job_id === job.job_id) ?? null
      : null;

  return (
    <div className="app-shell" id="dashboard">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open navigation"
            >
              <List size={23} />
            </button>
            <div className="breadcrumb">
              <span>Workspace</span>
              <span className="breadcrumb-separator">/</span>
              <strong>Dashboard</strong>
            </div>
          </div>

          <div className="topbar-actions">
            <span className={`api-status api-status-${apiStatus}`}>
              <span className="status-dot" />
              {apiStatus === "checking"
                ? "Checking API"
                : apiStatus === "online"
                  ? "Backend connected"
                  : "Backend offline"}
            </span>
            <button
              className="icon-button"
              aria-label="Notifications"
              title="Notifications are not configured"
            >
              <Bell size={20} />
            </button>
          </div>
        </header>

        <div className="dashboard-content">
          <section className="welcome-section">
            <div>
              <div className="welcome-kicker">
                <span className="welcome-kicker-line" />
                YOUR AI VIDEO WORKSPACE
              </div>
              <h1>
                Turn any topic into a <span>visual story.</span>
              </h1>
              <p>
                Research, scriptwriting, narration and rendering — brought
                together in one workflow.
              </p>
            </div>
            <a className="docs-link" href="#workflow">
              Explore workflow <ArrowUpRight size={16} />
            </a>
          </section>

          {notice && (
            <div
              className={`notice notice-${notice.kind}`}
              role="status"
              aria-live="polite"
            >
              {notice.kind === "error" ? (
                <WarningCircle size={20} />
              ) : (
                <CheckCircle size={20} />
              )}
              <span>{notice.text}</span>
              <button
                onClick={() => setNotice(null)}
                aria-label="Dismiss message"
              >
                ×
              </button>
            </div>
          )}

          <div className="dashboard-grid">
            <GenerationForm onGenerate={handleGenerate} busy={Boolean(busy)} />

            <div className="right-column">
              <WorkflowProgress
                status={job?.status ?? null}
                logs={job?.logs ?? []}
                error={job?.error ?? null}
              />
              <VideoPreview
                topic={job?.topic ?? null}
                status={job?.status ?? null}
                videoUrl={currentVideo?.videoUrl ?? null}
                error={job?.error ?? null}
              />
            </div>
          </div>

          <RecentVideos videos={recentVideos} />

          <footer className="page-footer">
            <span>Video Explainer Agent</span>
            <span>Built with LangGraph · Python · Remotion</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
