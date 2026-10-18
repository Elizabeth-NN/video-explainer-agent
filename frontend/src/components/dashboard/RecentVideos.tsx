import { FilmStrip, ArrowRight } from "@phosphor-icons/react";

export default function RecentVideos() {
  return (
    <section className="panel recent-panel" id="recent-videos">
      <div className="panel-heading panel-heading-compact">
        <div>
          <span className="eyebrow">YOUR LIBRARY</span>
          <h2>Recent videos</h2>
        </div>
        <span className="recent-count">0 videos</span>
      </div>

      <div className="recent-empty">
        <div className="recent-empty-icon"><FilmStrip size={24} /></div>
        <div>
          <strong>Your library is ready</strong>
          <p>When you generate a video, it will be listed here.</p>
        </div>
        <a href="#generation-form" className="text-link">Create your first video <ArrowRight size={16} /></a>
      </div>
    </section>
  );
}
