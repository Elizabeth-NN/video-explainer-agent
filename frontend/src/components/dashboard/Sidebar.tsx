"use client";

import {
  X,
  Plus,
  FilmStrip,
  GitBranch,
  GearSix,
  VideoCamera,
  House,
} from "@phosphor-icons/react";

type SidebarProps = {
  open: boolean;
  onClose: () => void;
};

export default function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {open && <button className="sidebar-backdrop" onClick={onClose} aria-label="Close navigation" />}

      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><VideoCamera size={24} weight="duotone" /></div>
          <div>
            <div className="brand-name">Video Explainer</div>
            <div className="brand-caption">AGENT STUDIO</div>
          </div>
          <button className="sidebar-close" onClick={onClose} aria-label="Close menu">
            <X size={20} />
          </button>
        </div>

        <button
          className="new-video-button"
          onClick={() => {
            onClose();
            document.getElementById("generation-form")?.scrollIntoView({ behavior: "smooth" });
          }}
        >
          <Plus size={19} weight="bold" />
          <span>New video</span>
        </button>

        <div className="nav-label">WORKSPACE</div>
        <nav className="sidebar-nav" aria-label="Main navigation">
          <a className="nav-item nav-item-active" href="#dashboard" onClick={onClose}>
            <House size={19} /> <span>Dashboard</span>
          </a>
          <a className="nav-item" href="#recent-videos" onClick={onClose}>
            <FilmStrip size={19} /> <span>My videos</span>
          </a>
          <a className="nav-item" href="#workflow" onClick={onClose}>
            <GitBranch size={19} /> <span>Workflow</span>
          </a>
          <a className="nav-item" href="#settings" onClick={onClose}>
            <GearSix size={19} /> <span>Settings</span>
          </a>
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-info-icon"><GitBranch size={19} /></div>
          <div className="sidebar-info-copy">
            <strong>LangGraph workflow</strong>
            <span>Research · Script · Scenes</span>
          </div>
          <span className="status-dot" aria-label="Workflow configured" />
          <p>Your explainer pipeline is configured. Generate a video to see its progress here.</p>
        </div>

        <div className="sidebar-footer">
          <div className="avatar">EN</div>
          <div className="profile-copy">
            <strong>Local workspace</strong>
            <span>Personal project</span>
          </div>
          <span className="local-badge">LOCAL</span>
        </div>
      </aside>
    </>
  );
}
