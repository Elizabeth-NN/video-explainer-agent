import { FilmStrip, ArrowRight, Download } from "@phosphor-icons/react";
import type { RecentVideo } from "./types";

type Props = {
  videos: RecentVideo[];
};

export default function RecentVideos({ videos }: Props) {
  return (
    <section className="panel recent-panel" id="recent-videos">
      <div className="panel-heading panel-heading-compact">
        <div>
          <span className="eyebrow">YOUR LIBRARY</span>
          <h2>Recent videos</h2>
        </div>
        <span className="recent-count">
          {videos.length} {videos.length === 1 ? "video" : "videos"}
        </span>
      </div>

      {videos.length === 0 ? (
        <div className="recent-empty">
          <div className="recent-empty-icon">
            <FilmStrip size={24} />
          </div>
          <div>
            <strong>Your library is ready</strong>
            <p>When you generate a video, it will be listed here.</p>
          </div>
          <a href="#generation-form" className="text-link">
            Create your first video <ArrowRight size={16} />
          </a>
        </div>
      ) : (
        <div className="recent-video-list">
          {videos.map((video) => (
            <article className="recent-video-item" key={video.job_id}>
              <div className="recent-empty-icon">
                <FilmStrip size={22} />
              </div>
              <div className="recent-video-copy">
                <strong>{video.topic}</strong>
                <span>Completed · MP4 video</span>
              </div>
              <a
                className="text-link"
                href={video.videoUrl}
                aria-label={`Download video about ${video.topic}`}
              >
                <Download size={17} /> Download
              </a>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
