import { MonitorPlay, Play, FilmStrip } from "@phosphor-icons/react";

export default function VideoPreview() {
  return (
    <section className="panel preview-panel">
      <div className="panel-heading panel-heading-compact">
        <div>
          <span className="eyebrow">YOUR OUTPUT</span>
          <h2>Video preview</h2>
        </div>
        <span className="preview-tag"><MonitorPlay size={15} /> Preview</span>
      </div>

      <div className="preview-canvas">
        <div className="preview-grid" />
        <div className="preview-empty-icon"><FilmStrip size={29} weight="duotone" /></div>
        <strong>Your next explainer starts here</strong>
        <span>Generated videos will appear in this area.</span>
        <div className="preview-play"><Play size={17} weight="fill" /></div>
      </div>

      <div className="preview-meta">
        <div>
          <strong>No video generated yet</strong>
          <span>Enter a topic to get started.</span>
        </div>
        <span className="empty-status">Waiting</span>
      </div>
    </section>
  );
}
