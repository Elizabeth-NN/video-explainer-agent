import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Illustration, pickIllustration, type IllustrationId, type Focus } from "./illustrations";
/* ──────────────────────────────────────────────────────────────
   Types
   ────────────────────────────────────────────────────────────── */

export type ColorName = "teal" | "gold" | "red" | "purple" | "white";

export type IconName =
  | "sun" | "panel" | "cell" | "bolt" | "inverter" | "house"
  | "syringe" | "virus" | "immune" | "shield" | "antibody"
  | "rna" | "protein" | "gear" | "link" | "check" | "dot" | "heart";

export type NodeSpec = { label: string; icon: IconName; color?: ColorName };

/**
 * What the scene generator should emit per scene (optional `visual`).
 * - flow: 2-4 nodes connected left to right, particles flow along the links
 * - hub:  one centre node with 2-6 satellites (inputs or outputs)
 * - bars: a small animated bar chart with count-up numbers
 */
export type VisualSpec =
  | { type: "flow"; title?: string; nodes: NodeSpec[]; footnote?: string }
  | { type: "illustration"; id: IllustrationId; title?: string; footnote?: string; focus?: Focus }
  | {
      type: "hub";
      title?: string;
      center: NodeSpec;
      satellites: NodeSpec[];
      direction?: "in" | "out";
      footnote?: string;
    }
  | {
      type: "bars";
      title?: string;
      bars: { label: string; value: number; color?: ColorName }[];
      suffix?: string;
      footnote?: string;
    };

export type ExplainerScene = {
  sceneNumber: number;
  narration: string;
  visualDescription: string;
  audioFile: string;
  durationInFrames: number;
  from: number;
  visual?: VisualSpec;
};

export type ExplainerProps = {
  topic: string;
  fps: number;
  width: number;
  height: number;
  scenes: ExplainerScene[];
};

/* ──────────────────────────────────────────────────────────────
   Palette + animation helpers
   ────────────────────────────────────────────────────────────── */

const C = {
  bg: "#0B1220",
  panel: "#17233A",
  teal: "#4FD1C5",
  gold: "#F2B84B",
  red: "#E87979",
  white: "#F4F6FA",
  muted: "#A6B0C2",
  purple: "#A78BFA",
};

const COLOR: Record<ColorName, string> = {
  teal: C.teal,
  gold: C.gold,
  red: C.red,
  purple: C.purple,
  white: C.white,
};

/** Frames of crossfade between scenes. */
const OVERLAP = 10;

const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const ease = Easing.bezier(0.22, 1, 0.36, 1);

/** 0 → 1 between `start` and `start + dur` frames, eased, clamped. */
const stage = (frame: number, start: number, dur = 20): number =>
  interpolate(frame, [start, start + Math.max(1, dur)], [0, 1], {
    ...CLAMP,
    easing: ease,
  });

/** fps-independent oscillation. hz = cycles per second. */
const osc = (t: number, hz: number, amp: number, phase = 0): number =>
  Math.sin(2 * Math.PI * hz * t + phase) * amp;

/** frame, fps, time in seconds, and a seconds→frames converter. */
const useT = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return { frame, fps, t: frame / fps, s: (sec: number) => sec * fps };
};

type Pt = [number, number];

const bezier = (a: Pt, c1: Pt, c2: Pt, b: Pt, p: number): Pt => {
  const u = 1 - p;
  return [
    u * u * u * a[0] + 3 * u * u * p * c1[0] + 3 * u * p * p * c2[0] + p * p * p * b[0],
    u * u * u * a[1] + 3 * u * u * p * c1[1] + 3 * u * p * p * c2[1] + p * p * p * b[1],
  ];
};

/* ──────────────────────────────────────────────────────────────
   Icons (drawn in a ±40 box, centred on 0,0)
   ────────────────────────────────────────────────────────────── */

type IconProps = { c: string; t: number };

const spokes = (n: number) => Array.from({ length: n }, (_, i) => (i * 360) / n);

const ICONS: Record<IconName, React.FC<IconProps>> = {
  heart: ({ c }) => (
    <path
      d="M0 31 C-8 23 -34 5 -34 -12 C-34 -29 -12 -34 0 -17 C12 -34 34 -29 34 -12 C34 5 8 23 0 31 Z"
      fill={c}
      stroke={c}
      strokeWidth="2"
    />
  ),

  sun: ({ c, t }) => (
    <g>
      <circle r="17" fill={c} />
      <g transform={`rotate(${t * 20})`}>
        {spokes(12).map((a) => (
          <path key={a} d="M0 -26 V-38" transform={`rotate(${a})`}
            stroke={c} strokeWidth="5" strokeLinecap="round" />
        ))}
      </g>
    </g>
  ),

  panel: ({ c }) => (
    <g transform="skewX(-8)">
      <rect x="-34" y="-24" width="68" height="48" rx="4"
        fill={c} fillOpacity=".18" stroke={c} strokeWidth="3" />
      <path d="M-11 -24 V24 M11 -24 V24 M-34 0 H34" stroke={c} strokeWidth="2" />
    </g>
  ),

  cell: ({ c, t }) => (
    <g>
      <rect x="-32" y="-26" width="64" height="52" rx="6"
        fill={c} fillOpacity=".15" stroke={c} strokeWidth="3" />
      {[0, 1, 2].map((i) => (
        <circle key={i} cx={-22 + ((t * 45 + i * 15) % 44)} cy={-14 + i * 14}
          r="4.5" fill={c} />
      ))}
    </g>
  ),

  bolt: ({ c }) => <path d="M6 -36 L-17 4 H-2 L-8 36 L18 -8 H4 Z" fill={c} />,

  inverter: ({ c }) => (
    <g>
      <rect x="-24" y="-32" width="48" height="64" rx="9"
        fill={c} fillOpacity=".15" stroke={c} strokeWidth="3" />
      <path d="M-12 -14 H12 M-12 -2 H12" stroke={c} strokeWidth="4" strokeLinecap="round" />
      <circle cy="17" r="5" fill={c} />
    </g>
  ),

  house: ({ c }) => (
    <g>
      <path d="M-36 0 L0 -32 L36 0" fill="none" stroke={c} strokeWidth="5"
        strokeLinecap="round" strokeLinejoin="round" />
      <path d="M-27 -5 V30 H27 V-5" fill={c} fillOpacity=".15" stroke={c} strokeWidth="3" />
      <rect x="-7" y="10" width="14" height="20" fill={c} fillOpacity=".5" />
    </g>
  ),

  syringe: ({ c }) => (
    <g transform="rotate(-35)">
      <rect x="-9" y="-30" width="18" height="46" rx="4"
        fill={c} fillOpacity=".2" stroke={c} strokeWidth="3" />
      <rect x="-6" y="-6" width="12" height="20" fill={c} fillOpacity=".7" />
      <path d="M0 16 V38 M0 -30 V-42 M-12 -42 H12" stroke={c} strokeWidth="3.5"
        strokeLinecap="round" />
    </g>
  ),

  virus: ({ c, t }) => (
    <g>
      {spokes(12).map((a) => (
        <path key={a} d="M0 -20 V-33" transform={`rotate(${a + t * 15})`}
          stroke={c} strokeWidth="5" strokeLinecap="round" />
      ))}
      <circle r="20" fill={c} fillOpacity=".35" stroke={c} strokeWidth="3" />
      <circle cx="-6" cy="-4" r="4" fill={C.white} fillOpacity=".8" />
      <circle cx="7" cy="6" r="3.5" fill={C.white} fillOpacity=".8" />
    </g>
  ),

  immune: ({ c, t }) => (
    <g>
      <circle r="31" fill={c} fillOpacity=".12" stroke={c} strokeWidth="3" />
      <circle r="14" fill={c} fillOpacity=".35" />
      {spokes(8).map((a) => (
        <circle key={a} r="4.5" fill={c}
          cx={Math.cos(((a + t * 25) * Math.PI) / 180) * 22}
          cy={Math.sin(((a + t * 25) * Math.PI) / 180) * 22} />
      ))}
    </g>
  ),

  shield: ({ c }) => (
    <g>
      <path d="M0 -36 L28 -25 V3 C28 21 14 31 0 38 C-14 31 -28 21 -28 3 V-25 Z"
        fill={c} fillOpacity=".15" stroke={c} strokeWidth="3.5" strokeLinejoin="round" />
      <path d="M-11 2 L-3 11 L12 -9" fill="none" stroke={c} strokeWidth="5"
        strokeLinecap="round" strokeLinejoin="round" />
    </g>
  ),

  antibody: ({ c }) => (
    <path d="M0 34 V2 M0 2 L-20 -28 M0 2 L20 -28" fill="none" stroke={c}
      strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" />
  ),

  rna: ({ c, t }) => {
    const strand = (phase: number) =>
      Array.from({ length: 13 }, (_, i) =>
        `${i ? "L" : "M"}${-36 + i * 6} ${Math.sin(i * 0.9 + phase + t * 3) * 14}`,
      ).join(" ");
    return (
      <g>
        <path d={strand(0)} fill="none" stroke={c} strokeWidth="6" strokeLinecap="round" />
        <path d={strand(Math.PI)} fill="none" stroke={c} strokeOpacity=".55"
          strokeWidth="6" strokeLinecap="round" />
      </g>
    );
  },

  protein: ({ c, t }) => {
    const blobs: [number, number, number][] = [
      [0, 0, 12], [-18, -10, 9], [16, -14, 8], [20, 10, 10],
      [-14, 16, 9], [0, -27, 6], [-27, 8, 6],
    ];
    return (
      <g>
        {blobs.map(([x, y, r], i) => (
          <circle key={i} cx={x} cy={y} r={r * (1 + osc(t, 0.5, 0.08, i))}
            fill={i % 2 ? C.gold : c} fillOpacity=".85" />
        ))}
      </g>
    );
  },

  gear: ({ c, t }) => (
    <g transform={`rotate(${t * 30})`}>
      {spokes(8).map((a) => (
        <rect key={a} x="-5" y="-33" width="10" height="13" rx="2" fill={c}
          transform={`rotate(${a})`} />
      ))}
      <circle r="22" fill="none" stroke={c} strokeWidth="6" />
      <circle r="6" fill={c} />
    </g>
  ),

  link: ({ c }) => (
    <g fill="none" stroke={c} strokeWidth="6">
      <circle cx="-13" r="17" />
      <circle cx="13" r="17" strokeOpacity=".65" />
    </g>
  ),

  check: ({ c }) => (
    <path d="M-24 0 L-8 18 L26 -20" fill="none" stroke={c} strokeWidth="9"
      strokeLinecap="round" strokeLinejoin="round" />
  ),

  dot: ({ c, t }) => (
    <g>
      <circle cx="-12" cy={-8 + osc(t, 0.6, 3)} r="10" fill={c} />
      <circle cx="13" cy={10 + osc(t, 0.6, 3, 2)} r="10" fill={c} />
      <circle cx="13" cy={-16 + osc(t, 0.6, 3, 4)} r="6" fill={c} />
    </g>
  ),
};

/* ──────────────────────────────────────────────────────────────
   Primitives: Node, Link, Footnote
   ────────────────────────────────────────────────────────────── */

const Node: React.FC<{
  x: number;
  y: number;
  r: number;
  spec: NodeSpec;
  delay: number;
  index: number;
  labelPos?: "below" | "above";
}> = ({ x, y, r, spec, delay, index, labelPos = "below" }) => {
  const { frame, t, s } = useT();
  const col = COLOR[spec.color ?? "teal"];
  const Icon = ICONS[spec.icon];

  const pop = stage(frame, delay, s(0.55));
  const ring = stage(frame, delay, s(0.9));
  const label = stage(frame, delay + s(0.3), s(0.4));
  const bob = osc(t, 0.35, 5, index * 1.7);
  const glow = 1 + osc(t, 0.6, 0.05, index);

  return (
    <g transform={`translate(${x} ${y + bob})`} opacity={pop}>
      <g transform={`scale(${0.6 + 0.4 * pop})`}>
        <circle r={r * glow} fill={col} fillOpacity=".08" />
        <circle r={r} fill={col} fillOpacity=".1" />
        <circle r={r} fill="none" stroke={col} strokeWidth="4"
          strokeLinecap="round" pathLength={1} strokeDasharray="1 1"
          strokeDashoffset={1 - ring} transform="rotate(-90)"
          opacity={ring > 0 ? 1 : 0} />
        <g transform={`scale(${r / 56})`}>
          <Icon c={col} t={t} />
        </g>
      </g>
      <text x="0" y={labelPos === "below" ? r + 32 : -(r + 16)}
        textAnchor="middle" fill={col} fontSize="20" letterSpacing="2"
        opacity={label}
        transform={`translate(0 ${(1 - label) * 8})`}>
        {spec.label}
      </text>
    </g>
  );
};

const Link: React.FC<{
  a: Pt;
  c1: Pt;
  c2: Pt;
  b: Pt;
  color: string;
  start: number;
  dur: number;
  particles?: number;
}> = ({ a, c1, c2, b, color, start, dur, particles = 4 }) => {
  const { frame, t, s } = useT();
  const draw = stage(frame, start, dur);
  const live = stage(frame, start + dur, s(0.4));
  const head = stage(frame, start + dur - 4, s(0.2));
  const angle = (Math.atan2(b[1] - c2[1], b[0] - c2[0]) * 180) / Math.PI;
  const d = `M${a[0]} ${a[1]} C${c1[0]} ${c1[1]} ${c2[0]} ${c2[1]} ${b[0]} ${b[1]}`;

  return (
    <g>
      <path d={d} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round"
        strokeOpacity=".8" pathLength={1} strokeDasharray="1 1"
        strokeDashoffset={1 - draw} opacity={draw > 0 ? 1 : 0} />
      <g transform={`translate(${b[0]} ${b[1]}) rotate(${angle})`} opacity={head}>
        <path d="M-14 -11 L0 0 L-14 11" fill="none" stroke={color} strokeWidth="4"
          strokeLinecap="round" strokeLinejoin="round" />
      </g>
      {live > 0 &&
        Array.from({ length: particles }, (_, i) => {
          const p = (t * 0.4 + i / particles) % 1;
          const [px, py] = bezier(a, c1, c2, b, p);
          return (
            <circle key={i} cx={px} cy={py} r="6" fill={color}
              opacity={Math.sin(p * Math.PI) * live} />
          );
        })}
    </g>
  );
};

const Footnote: React.FC<{ text?: string; at: number }> = ({ text, at }) => {
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

/* ──────────────────────────────────────────────────────────────
   Diagrams
   ────────────────────────────────────────────────────────────── */

type Spec<T extends VisualSpec["type"]> = Extract<VisualSpec, { type: T }>;

const FlowDiagram: React.FC<{ spec: Spec<"flow"> }> = ({ spec }) => {
  const { s } = useT();
  const n = spec.nodes.length;
  const margin = n <= 2 ? 260 : n === 3 ? 190 : 150;
  const r = n >= 4 ? 56 : 70;
  const y = 190;
  const step = s(0.7);
  const xs = spec.nodes.map((_, i) =>
    n === 1 ? 500 : margin + (i * (1000 - 2 * margin)) / (n - 1),
  );

  return (
    <>
      {spec.nodes.map((node, i) => (
        <Node key={i} x={xs[i]} y={y} r={r} spec={node} index={i}
          delay={s(0.2) + i * step} />
      ))}
      {xs.slice(0, -1).map((x, i) => {
        const a: Pt = [x + r + 12, y];
        const b: Pt = [xs[i + 1] - r - 12, y];
        const dx = b[0] - a[0];
        return (
          <Link key={i} a={a} b={b}
            c1={[a[0] + dx / 3, y - 30]} c2={[b[0] - dx / 3, y - 30]}
            color={COLOR[spec.nodes[i + 1].color ?? "teal"]}
            start={s(0.2) + i * step + s(0.5)} dur={s(0.7)} />
        );
      })}
      <Footnote text={spec.footnote} at={s(0.2) + n * step + s(0.4)} />
    </>
  );
};

const HubDiagram: React.FC<{ spec: Spec<"hub"> }> = ({ spec }) => {
  const { s } = useT();
  const cx = 500, cy = 195, rx = 330, ry = 118, R = 74, r = 46;
  const n = spec.satellites.length;
  const out = spec.direction === "out";

  return (
    <>
      <Node x={cx} y={cy} r={R} spec={spec.center} index={0}
        delay={s(0.2)} labelPos="above" />
      {spec.satellites.map((sp, i) => {
        const ang = -Math.PI / 2 + Math.PI / n + (i * 2 * Math.PI) / n;
        const x = cx + Math.cos(ang) * rx;
        const y = cy + Math.sin(ang) * ry;
        const delay = s(0.9) + i * s(0.25);

        const vx = x - cx, vy = y - cy;
        const len = Math.hypot(vx, vy);
        const ux = vx / len, uy = vy / len;
        const centerEdge: Pt = [cx + ux * (R + 14), cy + uy * (R + 14)];
        const satEdge: Pt = [x - ux * (r + 14), y - uy * (r + 14)];
        const a = out ? centerEdge : satEdge;
        const b = out ? satEdge : centerEdge;
        const c1: Pt = [a[0] + (b[0] - a[0]) / 3, a[1] + (b[1] - a[1]) / 3];
        const c2: Pt = [a[0] + ((b[0] - a[0]) * 2) / 3, a[1] + ((b[1] - a[1]) * 2) / 3];

        return (
          <React.Fragment key={i}>
            <Node x={x} y={y} r={r} spec={sp} index={i + 1} delay={delay}
              labelPos={y < cy ? "above" : "below"} />
            <Link a={a} b={b} c1={c1} c2={c2}
              color={COLOR[(out ? sp.color : spec.center.color) ?? "teal"]}
              start={delay + s(0.35)} dur={s(0.6)} particles={3} />
          </React.Fragment>
        );
      })}
      <Footnote text={spec.footnote} at={s(0.9) + n * s(0.25) + s(0.8)} />
    </>
  );
};

const BarsDiagram: React.FC<{ spec: Spec<"bars"> }> = ({ spec }) => {
  const { frame, s } = useT();
  const n = spec.bars.length;
  const baseY = 335, maxH = 230;
  const bw = n <= 3 ? 130 : 90;
  const gap = 60;
  const total = n * bw + (n - 1) * gap;
  const x0 = (1000 - total) / 2;
  const max = Math.max(...spec.bars.map((b) => b.value), 1);
  const base = stage(frame, 0, s(0.5));

  return (
    <>
      <path d={`M${x0 - 30} ${baseY} H${x0 + total + 30}`} stroke={C.muted}
        strokeWidth="3" strokeLinecap="round" pathLength={1}
        strokeDasharray="1 1" strokeDashoffset={1 - base}
        opacity={base > 0 ? 1 : 0} />
      {spec.bars.map((bar, i) => {
        const col = COLOR[bar.color ?? "teal"];
        const p = stage(frame, s(0.4) + i * s(0.3), s(0.9));
        const h = (bar.value / max) * maxH * p;
        const x = x0 + i * (bw + gap);
        return (
          <g key={i}>
            <rect x={x} y={baseY - h} width={bw} height={Math.max(h, 0)} rx="8"
              fill={col} fillOpacity=".25" stroke={col} strokeWidth="3" />
            <text x={x + bw / 2} y={baseY - h - 14} textAnchor="middle"
              fill={col} fontSize="28" fontWeight="700" opacity={p}>
              {Math.round(bar.value * p)}{spec.suffix ?? ""}
            </text>
            <text x={x + bw / 2} y={baseY + 34} textAnchor="middle"
              fill={C.muted} fontSize="19" opacity={stage(frame, s(0.6) + i * s(0.3), s(0.4))}>
              {bar.label}
            </text>
          </g>
        );
      })}
      <Footnote text={spec.footnote} at={s(0.4) + n * s(0.3) + s(0.8)} />
    </>
  );
};

const Diagram: React.FC<{ spec: VisualSpec; duration: number }> = ({ spec, duration }) => (
  <svg viewBox="0 0 1000 430" width="100%" height="100%">
    {spec.type === "flow" && <FlowDiagram spec={spec} />}
    {spec.type === "hub" && <HubDiagram spec={spec} />}
    {spec.type === "bars" && <BarsDiagram spec={spec} />}
    {spec.type === "illustration" && (
      <Illustration id={spec.id} duration={duration} focus={spec.focus} footnote={spec.footnote} />
    )}
  </svg>
);

/* ──────────────────────────────────────────────────────────────
   Spec resolution: scene.visual → topic preset → generic fallback
   Presets are plain data, so adding a topic never means new JSX.
   ────────────────────────────────────────────────────────────── */

const PRESETS: { match: RegExp; specs: VisualSpec[] }[] = [
  {
    match: /\b(solar|photovoltaic|photovoltaics)\b/i,
    specs: [
      {
        type: "flow", title: "Capturing Sunlight",
        nodes: [
          { label: "SUNLIGHT", icon: "sun", color: "gold" },
          { label: "SOLAR PANELS", icon: "panel", color: "teal" },
          { label: "YOUR HOME", icon: "house", color: "teal" },
        ],
      },
      {
        type: "hub", title: "Cells Work Together", direction: "in",
        center: { label: "SOLAR MODULE", icon: "panel", color: "teal" },
        satellites: [
          { label: "CELL", icon: "cell", color: "teal" },
          { label: "CELL", icon: "cell", color: "teal" },
          { label: "CELL", icon: "cell", color: "teal" },
          { label: "CELL", icon: "cell", color: "teal" },
        ],
        footnote: "Connected cells add up to usable power",
      },
      {
        type: "flow", title: "Inside a Solar Cell",
        nodes: [
          { label: "PHOTONS", icon: "sun", color: "gold" },
          { label: "SILICON CELL", icon: "cell", color: "teal" },
          { label: "ELECTRON FLOW", icon: "bolt", color: "gold" },
        ],
      },
      {
        type: "flow", title: "From DC to AC",
        nodes: [
          { label: "DC POWER", icon: "panel", color: "teal" },
          { label: "INVERTER", icon: "inverter", color: "gold" },
          { label: "AC POWER", icon: "house", color: "teal" },
        ],
        footnote: "DC electricity is converted to AC",
      },
      {
        type: "hub", title: "Powering Your Home", direction: "out",
        center: { label: "HOME", icon: "house", color: "teal" },
        satellites: [
          { label: "LIGHTS", icon: "bolt", color: "gold" },
          { label: "APPLIANCES", icon: "inverter", color: "teal" },
          { label: "DEVICES", icon: "gear", color: "purple" },
        ],
      },
    ],
  },
  {
    match: /\bvaccin\w*\b|\bimmuni[sz]ation\b/i,
    specs: [
      {
        type: "flow", title: "Meet the immune system",
        nodes: [
          { label: "IMMUNE DEFENSE", icon: "immune", color: "teal" },
          { label: "POTENTIAL THREAT", icon: "virus", color: "red" },
        ],
      },
      {
        type: "flow", title: "Introducing a vaccine",
        nodes: [
          { label: "VACCINE", icon: "syringe", color: "gold" },
          { label: "BODY'S CELLS", icon: "immune", color: "teal" },
        ],
      },
      {
        type: "flow", title: "Recognizing an antigen",
        nodes: [
          { label: "MICROBE-LIKE SHAPE", icon: "virus", color: "red" },
          { label: "SURFACE PROTEIN", icon: "protein", color: "teal" },
        ],
        footnote: "Different vaccines can present different antigens",
      },
      {
        type: "flow", title: "The immune response begins",
        nodes: [
          { label: "IMMUNE RECEPTOR", icon: "antibody", color: "teal" },
          { label: "ANTIGEN SIGNAL", icon: "virus", color: "red" },
        ],
      },
      {
        type: "flow", title: "Preparing for the future",
        nodes: [
          { label: "IMMUNE MEMORY", icon: "immune", color: "teal" },
          { label: "READY", icon: "shield", color: "gold" },
          { label: "FUTURE EXPOSURE", icon: "virus", color: "red" },
        ],
      },
      {
        type: "flow", title: "From mRNA to protein",
        nodes: [
          { label: "mRNA INSTRUCTIONS", icon: "rna", color: "gold" },
          { label: "CELL MACHINERY", icon: "gear", color: "teal" },
          { label: "PROTEIN PRODUCT", icon: "protein", color: "purple" },
        ],
      },
      {
        type: "flow", title: "Combining antigens",
        nodes: [
          { label: "WEAKER ANTIGEN", icon: "virus", color: "red" },
          { label: "JOINED", icon: "link", color: "gold" },
          { label: "CARRIER ANTIGEN", icon: "protein", color: "teal" },
        ],
      },
      {
        type: "hub", title: "Building immune memory", direction: "in",
        center: { label: "PATHOGEN", icon: "virus", color: "red" },
        satellites: [
          { label: "RECOGNITION", icon: "antibody", color: "teal" },
          { label: "RESPONSE", icon: "gear", color: "gold" },
          { label: "MEMORY", icon: "shield", color: "purple" },
        ],
      },
    ],
  },
];

const shortLabel = (text: string): string => {
  const words = text.replace(/[^\w\s'-]/g, "").split(/\s+/).filter(Boolean)
    .slice(0, 3).join(" ").toUpperCase();
  return words.length > 20 ? `${words.slice(0, 19)}…` : words;
};

/** Last resort for topics with no preset and no `visual` on the scene. */
const fallbackSpec = (scene: ExplainerScene): VisualSpec => {
  const icons: IconName[] = ["dot", "gear", "check"];
  const colors: ColorName[] = ["teal", "gold", "purple"];
  const parts = scene.narration
    .split(/[,;:.!?]\s*|\s+(?:and|then|so|which|because)\s+/i)
    .map((p) => p.trim())
    .filter((p) => p.split(/\s+/).length >= 2)
    .slice(0, 3);

  if (parts.length < 2) {
    return {
      type: "flow",
      nodes: [
        { label: "INPUT", icon: "dot", color: "teal" },
        { label: "PROCESS", icon: "gear", color: "gold" },
        { label: "OUTCOME", icon: "check", color: "purple" },
      ],
    };
  }
  return {
    type: "flow",
    nodes: parts.map((p, i) => ({ label: shortLabel(p), icon: icons[i], color: colors[i] })),
  };
};

/**
 * Choose solar illustrations by the actual concept being narrated,
 * rather than cycling through the topic's diagrams by scene number.
 */
const solarSpecForScene = (scene: ExplainerScene): VisualSpec => {
  const text = `${scene.narration} ${scene.visualDescription || ""}`;

  if (/\b(solar lighting|charge controller|LED lamp|lighting system)\b/i.test(text)) {
    return {
      type: "flow",
      title: "From Sunlight to Light",
      nodes: [
        { label: "SOLAR PANEL", icon: "panel", color: "gold" },
        { label: "BATTERY", icon: "cell", color: "teal" },
        { label: "LED LAMP", icon: "bolt", color: "gold" },
      ],
      footnote: "A controller manages charging in systems that include one",
    };
  }

  if (/\b(excited electrons?|electrons? become excited)\b/i.test(text)) {
    return {
      type: "flow",
      title: "What Light Does Inside a Cell",
      nodes: [
        { label: "LIGHT PHOTONS", icon: "sun", color: "gold" },
        { label: "SILICON CELL", icon: "cell", color: "teal" },
        { label: "EXCITED ELECTRONS", icon: "bolt", color: "gold" },
      ],
      footnote: "Light gives electrons energy inside photovoltaic material",
    };
  }

  if (/\b(flow through a circuit|electrons? flow|electrical circuit)\b/i.test(text)) {
    return {
      type: "flow",
      title: "Electrons Moving Through a Circuit",
      nodes: [
        { label: "SOLAR CELL", icon: "cell", color: "teal" },
        { label: "ELECTRON FLOW", icon: "bolt", color: "gold" },
        { label: "DC ELECTRICITY", icon: "gear", color: "purple" },
      ],
      footnote: "A connected circuit allows electric current to flow",
    };
  }

  if (/\b(batter(?:y|ies)|stored|storage)\b/i.test(text)) {
    return {
      type: "flow",
      title: "Storing Solar Energy",
      nodes: [
        { label: "SOLAR PANEL", icon: "panel", color: "gold" },
        { label: "CHARGE CONTROL", icon: "gear", color: "teal" },
        { label: "BATTERY STORAGE", icon: "cell", color: "purple" },
      ],
      footnote: "Storage requires a battery and a suitable system",
    };
  }

  if (/\b(direct current|DC electricity|\bDC\b)\b/i.test(text)) {
    return {
      type: "flow",
      title: "Electricity from Solar Cells",
      nodes: [
        { label: "SOLAR CELLS", icon: "cell", color: "teal" },
        { label: "DIRECT CURRENT", icon: "bolt", color: "gold" },
        { label: "CONNECTED CIRCUIT", icon: "gear", color: "purple" },
      ],
      footnote: "Solar cells produce direct current electricity",
    };
  }

  if (/\b(convert|conversion|light energy|electrical energy|photovoltaic)\b/i.test(text)) {
    return {
      type: "flow",
      title: "Converting Light into Electricity",
      nodes: [
        { label: "SUNLIGHT", icon: "sun", color: "gold" },
        { label: "SOLAR CELLS", icon: "cell", color: "teal" },
        { label: "ELECTRICAL ENERGY", icon: "bolt", color: "purple" },
      ],
      footnote: "Photovoltaic cells convert light energy into electrical energy",
    };
  }

  return {
    type: "flow",
    title: "Capturing Sunlight",
    nodes: [
      { label: "SUNLIGHT", icon: "sun", color: "gold" },
      { label: "SOLAR PANEL", icon: "panel", color: "teal" },
      { label: "ELECTRICITY", icon: "bolt", color: "purple" },
    ],
  };
};

/**
 * Choose vaccine illustrations from the concept in the current narration.
 * This works for both Gemini-written and fallback-written scripts.
 */
const vaccineSpecForScene = (scene: ExplainerScene): VisualSpec => {
  const text = `${scene.narration} ${scene.visualDescription || ""}`;

  if (/\b(memory|remember|future exposure|in the future|long.term protection)\b/i.test(text)) {
    return {
      type: "flow",
      title: "Building Immune Memory",
      nodes: [
        { label: "FIRST EXPOSURE", icon: "virus", color: "red" },
        { label: "IMMUNE MEMORY", icon: "immune", color: "teal" },
        { label: "FASTER RESPONSE", icon: "shield", color: "gold" },
      ],
      footnote: "Immune memory can help the body recognize a threat later",
    };
  }

  if (/\b(antibod|antigen|recogniz|recognis|bind|receptor)\w*\b/i.test(text)) {
    return {
      type: "flow",
      title: "Recognizing an Antigen",
      nodes: [
        { label: "ANTIGEN", icon: "virus", color: "red" },
        { label: "RECOGNITION", icon: "antibody", color: "teal" },
        { label: "IMMUNE RESPONSE", icon: "immune", color: "gold" },
      ],
      footnote: "Immune recognition depends on specific molecular features",
    };
  }

  if (/\b(mrna|messenger RNA|protein|cellular instructions)\b/i.test(text)) {
    return {
      type: "flow",
      title: "From mRNA to Protein",
      nodes: [
        { label: "mRNA", icon: "rna", color: "gold" },
        { label: "CELL MACHINERY", icon: "gear", color: "teal" },
        { label: "PROTEIN", icon: "protein", color: "purple" },
      ],
      footnote: "Some vaccines deliver instructions for making a target protein",
    };
  }

  if (/\b(immune system|immune cells?|defen[cs]e|respond|response|white blood cells?)\b/i.test(text)) {
    return {
      type: "flow",
      title: "The Immune Response",
      nodes: [
        { label: "POTENTIAL THREAT", icon: "virus", color: "red" },
        { label: "IMMUNE SYSTEM", icon: "immune", color: "teal" },
        { label: "BODY'S RESPONSE", icon: "shield", color: "gold" },
      ],
    };
  }

  if (/\b(vaccin\w*|injection|dose|immuni[sz]ation)\b/i.test(text)) {
    return {
      type: "flow",
      title: "Introducing a Vaccine",
      nodes: [
        { label: "VACCINE", icon: "syringe", color: "gold" },
        { label: "IMMUNE SYSTEM", icon: "immune", color: "teal" },
        { label: "PREPARED RESPONSE", icon: "shield", color: "purple" },
      ],
      footnote: "Vaccines help train the immune system to recognize a target",
    };
  }

  return {
    type: "flow",
    title: "Preparing Immune Defenses",
    nodes: [
      { label: "POTENTIAL THREAT", icon: "virus", color: "red" },
      { label: "IMMUNE DEFENSE", icon: "immune", color: "teal" },
      { label: "PROTECTION", icon: "shield", color: "gold" },
    ],
  };
};


const heartSpecForScene = (scene: ExplainerScene): VisualSpec => {
  const text = `${scene.narration} ${scene.visualDescription || ""}`;

  if (/venae cavae|returning from the body|enters the right side/i.test(text)) {
    return {
      type: "flow",
      title: "Returning Blood Enters the Heart",
      nodes: [
        { label: "BODY", icon: "dot", color: "gold" },
        { label: "VENAE CAVAE", icon: "gear", color: "teal" },
        { label: "RIGHT HEART", icon: "heart", color: "red" },
      ],
      footnote: "Blood returning from the body enters the right side",
    };
  }

  if (/pulmonary artery|right side.*lungs|blood to the lungs/i.test(text)) {
    return {
      type: "flow",
      title: "From the Heart to the Lungs",
      nodes: [
        { label: "RIGHT HEART", icon: "heart", color: "red" },
        { label: "PULMONARY ARTERY", icon: "dot", color: "red" },
        { label: "LUNGS", icon: "immune", color: "teal" },
      ],
      footnote: "The pulmonary artery carries blood toward the lungs",
    };
  }

  if (/left side|returning from the lungs|receives blood/i.test(text)) {
    return {
      type: "flow",
      title: "Blood Returns from the Lungs",
      nodes: [
        { label: "LUNGS", icon: "dot", color: "teal" },
        { label: "LEFT HEART", icon: "heart", color: "red" },
      ],
      footnote: "The left side receives blood returning from the lungs",
    };
  }

  if (/four chambers|four valves|muscular organ|anatomy/i.test(text)) {
    return {
      type: "hub",
      title: "Four Chambers and Four Valves",
      center: { label: "THE HEART", icon: "heart", color: "red" },
      direction: "in",
      satellites: [
        { label: "FOUR CHAMBERS", icon: "cell", color: "teal" },
        { label: "FOUR VALVES", icon: "gear", color: "gold" },
        { label: "BLOOD FLOW", icon: "dot", color: "purple" },
      ],
      footnote: "The valves help blood move through the heart",
    };
  }

  if (/blood vessels|around the body|tissues|oxygen|nutrients|carbon dioxide/i.test(text)) {
    return {
      type: "flow",
      title: "Blood Circulates Around the Body",
      nodes: [
        { label: "HEART", icon: "heart", color: "red" },
        { label: "BLOOD VESSELS", icon: "dot", color: "teal" },
        { label: "BODY TISSUES", icon: "cell", color: "gold" },
      ],
      footnote: "Blood transports oxygen and nutrients to body tissues",
    };
  }

  return {
    type: "hub",
    title: "The Heart and Circulation",
    center: { label: "THE HEART", icon: "heart", color: "red" },
    direction: "out",
    satellites: [
      { label: "BODY", icon: "dot", color: "gold" },
      { label: "LUNGS", icon: "immune", color: "teal" },
      { label: "BLOOD FLOW", icon: "gear", color: "purple" },
    ],
    footnote: "The heart pumps blood through the circulatory system",
  };
};

const resolveSpec = (scene: ExplainerScene, topic: string): VisualSpec => {
  if (scene.visual) return scene.visual;

  const sceneText = `${scene.narration} ${scene.visualDescription || ""}`;
  const pick = pickIllustration(topic, sceneText);
  if (pick) return { type: "illustration", ...pick };
  const isSolar = /\b(solar|photovoltaic|photovoltaics|sunlight)\b/i.test(
    `${topic} ${sceneText}`,
  );

  if (isSolar) return solarSpecForScene(scene);

  const heartTopic = /\b(heart|cardiac)\b/i.test(topic);
  if (heartTopic) return heartSpecForScene(scene);

  const vaccineTopic = /\b(vaccin\w*|immuni[sz]ation)\b/i.test(
    `${topic} ${sceneText}`,
  );
  if (vaccineTopic) return vaccineSpecForScene(scene);

  const preset = PRESETS.find((p) => p.match.test(topic));
  if (preset) return preset.specs[(scene.sceneNumber - 1) % preset.specs.length];

  return fallbackSpec(scene);
};

const sceneTitle = (spec: VisualSpec, scene: ExplainerScene): string => {
  if (spec.title) return spec.title;
  const first = scene.narration.split(/[.!?;:]/)[0].trim();
  if (!first) return `Key idea ${scene.sceneNumber}`;
  return first.length > 44 ? `${first.slice(0, 41).trimEnd()}…` : first;
};

/* ──────────────────────────────────────────────────────────────
   Scene chrome
   ────────────────────────────────────────────────────────────── */

const Ambient: React.FC = () => {
  const { t } = useT();
  const dots = useMemo(
    () =>
      Array.from({ length: 18 }, (_, i) => ({
        x: (i * 137.5) % 100,
        y: (i * 61.8) % 100,
        size: 3 + (i % 3) * 2,
        hz: 0.04 + (i % 5) * 0.015,
        amp: 10 + (i % 4) * 6,
      })),
    [],
  );
  return (
    <>
      {dots.map((d, i) => (
        <div key={i} style={{
          position: "absolute", left: `${d.x}%`, top: `${d.y}%`,
          width: d.size, height: d.size, borderRadius: "50%",
          background: C.teal, opacity: 0.12,
          transform: `translate(${osc(t, d.hz, d.amp, i)}px, ${osc(t, d.hz * 1.3, d.amp, i * 2)}px)`,
        }} />
      ))}
    </>
  );
};

const Caption: React.FC<{ text: string; duration: number }> = ({ text, duration }) => {
  const { frame, s } = useT();
  const words = useMemo(() => text.split(/\s+/).filter(Boolean), [text]);
  const startAt = s(0.35);
  const per = Math.max(1, (duration * 0.88 - startAt) / words.length);
  const active = Math.floor((frame - startAt) / per);

  return (
    <div style={{ fontSize: text.length > 150 ? 19 : 22, lineHeight: 1.4, fontWeight: 500 }}>
      {words.map((w, i) => {
        const st = startAt + i * per;
        const rev = interpolate(frame, [st, st + 5], [0, 1], CLAMP);
        return (
          <span key={i} style={{
            display: "inline-block", marginRight: "0.28em",
            opacity: 0.2 + 0.8 * rev,
            transform: `translateY(${(1 - rev) * 4}px)`,
            color: i === active ? C.teal : C.white,
          }}>
            {w}
          </span>
        );
      })}
    </div>
  );
};

const Scene: React.FC<{ scene: ExplainerScene; topic: string; totalScenes: number }> = ({
  scene, topic, totalScenes,
}) => {
  const { frame, s } = useT();
  const spec = useMemo(() => resolveSpec(scene, topic), [scene, topic]);
  const title = sceneTitle(spec, scene);

  // Fade in only; the outgoing scene stays mounted underneath for OVERLAP frames.
  const fadeIn = interpolate(frame, [0, OVERLAP], [0, 1], CLAMP);
  const head = stage(frame, 0, s(0.7));
  const titleIn = stage(frame, 5, s(0.7));
  const panelIn = stage(frame, 8, s(0.7));
  const drift = interpolate(frame, [0, scene.durationInFrames + OVERLAP], [1, 1.035], CLAMP);

  return (
    <AbsoluteFill style={{
      background: `radial-gradient(ellipse at 50% 45%, #172943 0%, ${C.bg} 72%)`,
      color: C.white,
      fontFamily: "Arial, Helvetica, sans-serif",
      opacity: fadeIn,
      overflow: "hidden",
    }}>
      <Ambient />

      <div style={{
        position: "absolute", top: 0, left: 0, right: 0, height: 6,
        background: `linear-gradient(90deg, ${C.teal}, ${C.gold}, ${C.red})`,
        transformOrigin: "left",
        transform: `scaleX(${Math.min(1, (frame + 1) / scene.durationInFrames)})`,
      }} />

      <div style={{
        position: "absolute", top: 35, left: 64, right: 64,
        display: "flex", justifyContent: "space-between",
        fontSize: 15, color: C.muted, letterSpacing: 3, opacity: head,
      }}>
        <span>FIELD NOTES / EXPLAINED</span>
        <span>{String(scene.sceneNumber).padStart(2, "0")} / {String(totalScenes).padStart(2, "0")}</span>
      </div>

      <div style={{
        position: "absolute", top: 82, left: 72, right: 72, textAlign: "center",
        opacity: titleIn,
        transform: `translateY(${(1 - titleIn) * 18}px)`,
      }}>
        <div style={{
          color: C.teal, fontSize: 14, letterSpacing: 5,
          textTransform: "uppercase", marginBottom: 10,
        }}>{topic}</div>
        <div style={{ fontSize: 39, lineHeight: 1.15, fontWeight: 700, letterSpacing: -0.7 }}>
          {title}
        </div>
      </div>

      <div style={{
        position: "absolute", top: 165, left: 95, right: 95, height: 355,
        transform: `scale(${(0.96 + 0.04 * panelIn) * drift})`,
        transformOrigin: "center",
      }}>
        <Diagram spec={spec} duration={scene.durationInFrames} />
      </div>

      <div style={{
        position: "absolute", left: 100, right: 100, bottom: 38,
        minHeight: 105, boxSizing: "border-box",
        padding: "20px 30px", borderRadius: 16,
        border: "1px solid #33445C", borderLeft: `5px solid ${C.teal}`,
        background: "rgba(18, 27, 46, .94)",
        display: "flex", alignItems: "center", justifyContent: "center",
        textAlign: "center",
        opacity: panelIn,
        transform: `translateY(${(1 - panelIn) * 15}px)`,
      }}>
        <Caption text={scene.narration} duration={scene.durationInFrames} />
      </div>
    </AbsoluteFill>
  );
};

/* ──────────────────────────────────────────────────────────────
   Root composition
   ────────────────────────────────────────────────────────────── */

export const Explainer: React.FC<ExplainerProps> = ({ topic, scenes }) => (
  <AbsoluteFill style={{ backgroundColor: C.bg }}>
    {scenes.map((scene) => (
      <React.Fragment key={scene.sceneNumber}>
        <Sequence
          from={scene.from}
          durationInFrames={scene.durationInFrames + OVERLAP}
          name={`Scene ${scene.sceneNumber}`}
        >
          <Scene scene={scene} topic={topic} totalScenes={scenes.length} />
        </Sequence>
        <Sequence
          from={scene.from}
          durationInFrames={scene.durationInFrames}
          name={`Audio ${scene.sceneNumber}`}
        >
          <Audio
            src={staticFile(scene.audioFile)}
            volume={(f) =>
              interpolate(f, [0, 3, scene.durationInFrames - 6, scene.durationInFrames],
                [0, 1, 1, 0], CLAMP)
            }
          />
        </Sequence>
      </React.Fragment>
    ))}
  </AbsoluteFill>
);