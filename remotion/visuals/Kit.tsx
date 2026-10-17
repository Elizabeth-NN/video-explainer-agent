/**
 * Shared primitives. Explainer.tsx should import these instead of defining its own,
 * so the built-in visuals and the library visuals can never drift apart.
 */
import React from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

export const C = {
  bg: "#0B1220",
  panel: "#17233A",
  teal: "#4FD1C5",
  gold: "#F2B84B",
  red: "#E87979",
  white: "#F4F6FA",
  muted: "#A6B0C2",
  purple: "#A78BFA",
};

export type ColorName = "teal" | "gold" | "red" | "purple" | "white";

export const COLOR: Record<ColorName, string> = {
  teal: C.teal,
  gold: C.gold,
  red: C.red,
  purple: C.purple,
  white: C.white,
};

export const ACCENTS = [C.teal, C.gold, C.purple, C.red];

export const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const ease = Easing.bezier(0.22, 1, 0.36, 1);

/** 0 → 1 between `start` and `start + dur` frames, eased, clamped. */
export const stage = (frame: number, start: number, dur = 20): number =>
  interpolate(frame, [start, start + Math.max(1, dur)], [0, 1], { ...CLAMP, easing: ease });

/** fps-independent oscillation. hz = cycles per second. */
export const osc = (t: number, hz: number, amp: number, phase = 0): number =>
  Math.sin(2 * Math.PI * hz * t + phase) * amp;

/** frame, fps, time in seconds, and a seconds→frames converter. */
export const useT = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return { frame, fps, t: frame / fps, s: (sec: number) => sec * fps };
};

export type Pt = [number, number];

/** SVG text doesn't wrap, so split into at most `maxLines` lines of about `max` chars. */
export const wrap = (text: string, max: number, maxLines = 2): string[] => {
  const lines: string[] = [];
  let cur = "";
  for (const w of text.split(/\s+/).filter(Boolean)) {
    if (cur && (cur + " " + w).length > max) {
      lines.push(cur);
      cur = w;
    } else cur = cur ? `${cur} ${w}` : w;
  }
  if (cur) lines.push(cur);
  if (lines.length > maxLines) {
    lines.length = maxLines;
    lines[maxLines - 1] = lines[maxLines - 1].slice(0, Math.max(1, max - 1)) + "…";
  }
  return lines;
};

export const clip = (text: string, max: number): string =>
  text.length > max ? `${text.slice(0, Math.max(1, max - 1))}…` : text;

/** Path for an arrow head whose tip is (x, y) and which points along unit vector (ux, uy). */
export const arrowPath = (x: number, y: number, ux: number, uy: number): string =>
  `M${x - ux * 10 - uy * 6} ${y - uy * 10 + ux * 6} L${x} ${y} L${x - ux * 10 + uy * 6} ${y - uy * 10 - ux * 6}`;

export const Footnote: React.FC<{ text?: string; at: number }> = ({ text, at }) => {
  const { frame, s } = useT();
  if (!text) return null;
  const p = stage(frame, at, s(0.5));
  return (
    <text x="500" y="414" textAnchor="middle" fill={C.muted} fontSize="17"
      opacity={p} transform={`translate(0 ${(1 - p) * 6})`}>
      {text}
    </text>
  );
};

/** One-line explanation of the current step of a trace. Sits above the footnote. */
export const Note: React.FC<{ text?: string }> = ({ text }) =>
  text ? (
    <text x="500" y="388" textAnchor="middle" fill={C.white} fontSize="21" fontWeight="600">
      {text}
    </text>
  ) : null;

/**
 * Step through a precomputed trace across the scene.
 * Returns the current frame of the trace, its index, and 0..1 progress inside the step.
 */
export const useTrace = <T,>(
  frames: T[],
  duration: number,
): { frame: T; index: number; progress: number } => {
  const { frame: f, s } = useT();
  const start = s(0.8);
  const end = Math.max(start + 1, duration * 0.88);
  const per = (end - start) / Math.max(1, frames.length);
  const raw = (f - start) / per;
  const index = Math.min(frames.length - 1, Math.max(0, Math.floor(raw)));
  const progress = Math.min(1, Math.max(0, raw - index));
  return { frame: frames[index], index, progress };
};
