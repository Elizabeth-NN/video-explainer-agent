import {
  MagnifyingGlass,
  PencilLine,
  ShieldCheck,
  SquaresFour,
  Waveform,
  FilmStrip,
  CircleDashed,
  CheckCircle,
  WarningCircle,
} from "@phosphor-icons/react";
import type { JobStatus } from "./types";

const stages = [
  {
    title: "Research topic",
    description: "Gather relevant source material",
    icon: MagnifyingGlass,
    keywords: ["research", "source", "wikipedia"],
  },
  {
    title: "Write the script",
    description: "Turn research into a clear explanation",
    icon: PencilLine,
    keywords: ["script", "writing", "writer"],
  },
  {
    title: "Review content",
    description: "Check quality and revise if needed",
    icon: ShieldCheck,
    keywords: ["critic", "review", "revision", "revise", "approved"],
  },
  {
    title: "Plan scenes",
    description: "Map the script to visual scenes",
    icon: SquaresFour,
    keywords: ["scene", "planning", "planner"],
  },
  {
    title: "Create narration",
    description: "Generate voice-over audio",
    icon: Waveform,
    keywords: ["narration", "audio", "speech", "tts", "voice"],
  },
  {
    title: "Render video",
    description: "Assemble scenes into a video",
    icon: FilmStrip,
    keywords: ["render", "ffmpeg", "video", "mp4"],
  },
];

type Props = {
  status: JobStatus | null;
  logs: string[];
  error: string | null;
};

export default function WorkflowProgress({ status, logs, error }: Props) {
  const combinedLogs = logs.join("\n").toLowerCase();

  let activeStage = -1;

  for (let index = stages.length - 1; index >= 0; index--) {
    if (stages[index].keywords.some((word) => combinedLogs.includes(word))) {
      activeStage = index;
      break;
    }
  }

  const isTerminal = status === "completed" || status === "failed";

  return (
    <section className="panel workflow-panel" id="workflow">
      <div className="panel-heading panel-heading-compact">
        <div>
          <span className="eyebrow">UNDER THE HOOD</span>
          <h2>Workflow</h2>
        </div>
        <span className={`idle-pill workflow-status-${status ?? "idle"}`}>
          {status === "completed" ? (
            <CheckCircle size={14} />
          ) : status === "failed" ? (
            <WarningCircle size={14} />
          ) : (
            <CircleDashed size={14} />
          )}
          {status === "queued"
            ? "Queued"
            : status === "running"
              ? "Running"
              : status === "completed"
                ? "Completed"
                : status === "failed"
                  ? "Failed"
                  : "Idle"}
        </span>
      </div>

      <p className="workflow-intro">
        {status
          ? `Current job: ${status}. Progress is inferred from the backend logs.`
          : "Your LangGraph pipeline moves through these stages for each video."}
      </p>

      <ol className="workflow-list">
        {stages.map((stage, index) => {
          const Icon = stage.icon;
          const stageState =
            status === "completed"
              ? "completed"
              : status === "failed" && index === activeStage
                ? "failed"
                : status === "running" &&
                    (index === activeStage ||
                      (activeStage >= 0 && index < activeStage))
                  ? index === activeStage
                    ? "active"
                    : "completed"
                  : status === "queued" && index === 0
                    ? "active"
                    : "pending";

          return (
            <li
              className={`workflow-stage stage-${stageState}`}
              key={stage.title}
            >
              <div className="stage-icon">
                {stageState === "completed" ? (
                  <CheckCircle size={19} />
                ) : stageState === "failed" ? (
                  <WarningCircle size={19} />
                ) : (
                  <Icon size={19} />
                )}
              </div>
              <div className="stage-copy">
                <strong>{stage.title}</strong>
                <span>
                  {stageState === "active"
                    ? status === "queued"
                      ? "Waiting to start"
                      : "In progress"
                    : stageState === "completed"
                      ? "Completed"
                      : stageState === "failed"
                        ? "Failed"
                        : stage.description}
                </span>
              </div>
              <span className="stage-number">
                {String(index + 1).padStart(2, "0")}
              </span>
            </li>
          );
        })}
      </ol>

      {logs.length > 0 && (
        <details className="workflow-logs">
          <summary>Latest backend logs ({logs.length})</summary>
          <pre>{logs.slice(-12).join("\n")}</pre>
        </details>
      )}

      {error && <p className="workflow-error">{error}</p>}

      <div className="workflow-footer">
        <div className="status-dot" />
        <span>
          {status === "completed"
            ? "Video generation finished"
            : status === "failed"
              ? "Generation needs attention"
              : status === "running"
                ? "Receiving backend updates"
                : status === "queued"
                  ? "Job accepted by the backend"
                  : isTerminal
                    ? "Generation finished"
                    : "Waiting for a generation request"}
        </span>
      </div>
    </section>
  );
}
