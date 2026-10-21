"use client";

import { useState, type FormEvent } from "react";
import { CaretDown, Sparkle, Lightning } from "@phosphor-icons/react";
import type { GenerationSettings } from "./types";

type Props = {
  onGenerate: (settings: GenerationSettings) => void;
  busy: boolean;
};

export default function GenerationForm({ onGenerate, busy }: Props) {
  const [topic, setTopic] = useState("");
  const [category, setCategory] = useState<"cs" | "physics">("cs");
  const [model, setModel] = useState<"standard" | "gemini">("standard");
  const [voice, setVoice] = useState("en-US-JennyNeural");
  const [format, setFormat] = useState<"landscape" | "vertical">("landscape");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!topic.trim() || busy) return;

    onGenerate({
      topic: topic.trim(),
      category,
      model,
      voice,
      format,
    });
  }

  return (
    <section className="panel generation-panel" id="generation-form">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">CREATE SOMETHING NEW</span>
          <h2>Generate a video</h2>
          <p>Start with a topic. Your agent handles the rest.</p>
        </div>
        <div className="heading-icon"><Sparkle size={23} weight="duotone" /></div>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="field-group">
          <label className="field-label" htmlFor="video-category">Video category</label>
          <div className="select-wrap">
            <select id="video-category" value={category} onChange={(event) => setCategory(event.target.value as "cs" | "physics")}>
              <option value="cs">Computer Science</option>
              <option value="physics">Physics</option>
            </select>
            <CaretDown size={17} />
          </div>
          <span className="helper-text">Choose the subject area for your explainer.</span>
        </div>

        <label className="field-label" htmlFor="video-topic">What should your video explain?</label>
        <textarea
          id="video-topic"
          className="topic-input"
          value={topic}
          onChange={(event) => setTopic(event.target.value)}
          placeholder="e.g. How solar panels turn sunlight into electricity..."
          rows={4}
          minLength={3}
          maxLength={300}
          required
        />
        <div className="field-footnote">
          <span>Be specific for a more focused explanation.</span>
          <span>{topic.length}/300</span>
        </div>

        <div className="field-group">
          <span className="field-label">Generation engine</span>
          <div className="engine-options">
            <button
              type="button"
              className={`engine-option ${model === "standard" ? "engine-selected" : ""}`}
              onClick={() => setModel("standard")}
              aria-pressed={model === "standard"}
            >
              <div className="engine-icon engine-icon-blue"><Lightning size={19} weight="duotone" /></div>
              <div className="engine-copy">
                <strong>Standard</strong>
                <span>Default workflow</span>
              </div>
              <span className="choice-indicator" />
            </button>

            <button
              type="button"
              className={`engine-option ${model === "gemini" ? "engine-selected" : ""}`}
              onClick={() => setModel("gemini")}
              aria-pressed={model === "gemini"}
            >
              <div className="engine-icon engine-icon-purple"><Sparkle size={19} weight="duotone" /></div>
              <div className="engine-copy">
                <strong>Gemini</strong>
                <span>AI-assisted writing</span>
              </div>
              <span className="choice-indicator" />
            </button>
          </div>
        </div>

        <div className="field-group">
          <label className="field-label" htmlFor="narration-voice">Narration voice</label>
          <div className="select-wrap">
            <select id="narration-voice" value={voice} onChange={(event) => setVoice(event.target.value)}>
              <option value="en-US-JennyNeural">Jenny · US English (recommended)</option>
              <option value="en-US-AriaNeural">Aria · US English</option>
            </select>
            <CaretDown size={17} />
          </div>
          <span className="helper-text">The selected voice will narrate the explanation.</span>
        </div>

        <div className="field-group">
          <span className="field-label">Video layout</span>
          <div className="format-options">
            <button
              type="button"
              className={`format-option ${format === "landscape" ? "format-selected" : ""}`}
              onClick={() => setFormat("landscape")}
              aria-pressed={format === "landscape"}
            >
              <span className="format-preview format-preview-wide"><span /></span>
              <span><strong>Landscape</strong><small>16:9 · YouTube</small></span>
              <span className="choice-indicator" />
            </button>
            <button
              type="button"
              className={`format-option ${format === "vertical" ? "format-selected" : ""}`}
              onClick={() => setFormat("vertical")}
              aria-pressed={format === "vertical"}
            >
              <span className="format-preview format-preview-tall"><span /></span>
              <span><strong>Vertical</strong><small>9:16 · Shorts</small></span>
              <span className="choice-indicator" />
            </button>
          </div>
          <span className="helper-text">Layout selection is a UI preview for now; renderer support comes next.</span>
        </div>

        <button className="generate-button" type="submit" disabled={busy || !topic.trim()}>
          <Sparkle size={19} weight="bold" />
          {busy ? "Preparing..." : "Generate video"}
        </button>
        <p className="form-note">Generation runs locally through your configured backend.</p>
      </form>
    </section>
  );
}
