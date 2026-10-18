import {
  MagnifyingGlass,
  PencilLine,
  ShieldCheck,
  SquaresFour,
  Waveform,
  FilmStrip,
  CircleDashed,
} from "@phosphor-icons/react";

const stages = [
  { title: "Research topic", description: "Gather relevant source material", icon: MagnifyingGlass },
  { title: "Write the script", description: "Turn research into a clear explanation", icon: PencilLine },
  { title: "Review content", description: "Check quality and revise if needed", icon: ShieldCheck },
  { title: "Plan scenes", description: "Map the script to visual scenes", icon: SquaresFour },
  { title: "Create narration", description: "Generate voice-over audio", icon: Waveform },
  { title: "Render video", description: "Assemble scenes into a video", icon: FilmStrip },
];

export default function WorkflowProgress() {
  return (
    <section className="panel workflow-panel" id="workflow">
      <div className="panel-heading panel-heading-compact">
        <div>
          <span className="eyebrow">UNDER THE HOOD</span>
          <h2>Workflow</h2>
        </div>
        <span className="idle-pill"><CircleDashed size={14} /> Idle</span>
      </div>

      <p className="workflow-intro">Your LangGraph pipeline moves through these stages for each video.</p>

      <ol className="workflow-list">
        {stages.map((stage, index) => {
          const Icon = stage.icon;
          return (
            <li className="workflow-stage" key={stage.title}>
              <div className="stage-icon"><Icon size={19} /></div>
              <div className="stage-copy">
                <strong>{stage.title}</strong>
                <span>{stage.description}</span>
              </div>
              <span className="stage-number">{String(index + 1).padStart(2, "0")}</span>
            </li>
          );
        })}
      </ol>

      <div className="workflow-footer">
        <div className="status-dot" />
        <span>Waiting for a generation request</span>
      </div>
    </section>
  );
}
