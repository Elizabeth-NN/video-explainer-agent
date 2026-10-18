import { MonitorPlay, Play, FilmStrip, Download } from "@phosphor-icons/react";
import type { JobStatus } from "./types";

type Props = {
  topic: string | null;
  status: JobStatus | null;
  videoUrl: string | null;
  error: string | null;
};

export default function VideoPreview({
  topic,
  status,
  videoUrl,
  error,
}: Props) {
  const statusLabel =
    status === "completed"
      ? "Ready"
      : status === "failed"
        ? "Failed"
        : status === "running"
          ? "Generating"
          : status === "queued"
            ? "Queued"
            : "Waiting";

  return (
    <section className="panel preview-panel">
      <div className="panel-heading panel-heading-compact">
        <div>
          <span className="eyebrow">YOUR OUTPUT</span>
          <h2>Video preview</h2>
        </div>
        <span className="preview-tag">
          <MonitorPlay size={15} /> Preview
        </span>
      </div>

      <div className="preview-canvas">
        {videoUrl ? (
          <video
            className="generated-video"
            src={videoUrl}
            controls
            preload="metadata"
            aria-label={`Generated explainer video: ${topic ?? "video"}`}
          >
            Your browser does not support video playback.
          </video>
        ) : (
          <>
            <div className="preview-grid" />
            <div className="preview-empty-icon">
              <FilmStrip size={29} weight="duotone" />
            </div>
            <strong>
              {status === "failed"
                ? "Video generation failed"
                : status === "running" || status === "queued"
                  ? "Your video is being prepared"
                  : "Your next explainer starts here"}
            </strong>
            <span>
              {error ||
                (status === "running" || status === "queued"
                  ? "Follow the workflow panel for updates."
                  : "Generated videos will appear in this area.")}
            </span>
            <div className="preview-play">
              <Play size={17} weight="fill" />
            </div>
          </>
        )}
      </div>

      <div className="preview-meta">
        <div>
          <strong>{topic ?? "No video generated yet"}</strong>
          <span>
            {videoUrl
              ? "Your video is ready to watch."
              : status
                ? `Job status: ${status}`
                : "Enter a topic to get started."}
          </span>
        </div>
        <span className="empty-status">{statusLabel}</span>
      </div>

      {videoUrl && (
        <a className="text-link video-download-link" href={videoUrl}>
          <Download size={17} /> Download video
        </a>
      )}
    </section>
  );
}
