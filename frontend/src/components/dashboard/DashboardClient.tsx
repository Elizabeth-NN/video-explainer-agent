"use client";

import { useEffect, useState } from "react";
import { Bell, List, ArrowUpRight, CheckCircle, WarningCircle } from "@phosphor-icons/react";
import Sidebar from "./Sidebar";
import GenerationForm from "./GenerationForm";
import WorkflowProgress from "./WorkflowProgress";
import VideoPreview from "./VideoPreview";
import RecentVideos from "./RecentVideos";
import type { GenerationSettings } from "./types";

type ApiStatus = "checking" | "online" | "offline";

export default function DashboardClient() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [notice, setNotice] = useState<{ kind: "info" | "error"; text: string } | null>(null);

  useEffect(() => {
    let active = true;

    async function checkApi() {
      try {
        const response = await fetch(
          process.env.NEXT_PUBLIC_API_BASE_URL
            ? `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/health`
            : "http://127.0.0.1:8000/api/health",
          { cache: "no-store" },
        );

        if (!response.ok) throw new Error("API health check failed");
        if (active) setApiStatus("online");
      } catch {
        if (active) setApiStatus("offline");
      }
    }

    checkApi();
    return () => {
      active = false;
    };
  }, []);

  function handleGenerate(settings: GenerationSettings) {
    setNotice({
      kind: "info",
      text: `Your topic is ready: “${settings.topic}”. The next step is connecting this form to the backend generation endpoint.`,
    });
  }

  return (
    <div className="app-shell" id="dashboard">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-left">
            <button className="mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="Open navigation">
              <List size={23} />
            </button>
            <div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-separator">/</span><strong>Dashboard</strong></div>
          </div>
          <div className="topbar-actions">
            <span className={`api-status api-status-${apiStatus}`}>
              <span className="status-dot" />
              {apiStatus === "checking" ? "Checking API" : apiStatus === "online" ? "Backend connected" : "Backend offline"}
            </span>
            <button className="icon-button" aria-label="Notifications" title="Notifications are not configured">
              <Bell size={20} />
            </button>
          </div>
        </header>

        <div className="dashboard-content">
          <section className="welcome-section">
            <div>
              <div className="welcome-kicker"><span className="welcome-kicker-line" /> YOUR AI VIDEO WORKSPACE</div>
              <h1>Turn any topic into a <span>visual story.</span></h1>
              <p>Research, scriptwriting, narration and rendering — brought together in one workflow.</p>
            </div>
            <a className="docs-link" href="#workflow">Explore workflow <ArrowUpRight size={16} /></a>
          </section>

          {notice && (
            <div className={`notice notice-${notice.kind}`} role="status">
              {notice.kind === "error" ? <WarningCircle size={20} /> : <CheckCircle size={20} />}
              <span>{notice.text}</span>
              <button onClick={() => setNotice(null)} aria-label="Dismiss message">×</button>
            </div>
          )}

          <div className="dashboard-grid">
            <GenerationForm onGenerate={handleGenerate} busy={false} />
            <div className="right-column">
              <WorkflowProgress />
              <VideoPreview />
            </div>
          </div>

          <RecentVideos />

          <footer className="page-footer">
            <span>Video Explainer Agent</span>
            <span>Built with LangGraph · Python · Remotion</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
