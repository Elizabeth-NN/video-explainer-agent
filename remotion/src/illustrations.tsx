import React, { createContext, useContext } from "react";
import { Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

/* ──────────────────────────────────────────────────────────────
   Public API
   ────────────────────────────────────────────────────────────── */

export type IllustrationId =
  | "solar-cell"
  | "solar-home"
  | "heart"
  | "immune-response"
  | "mrna-protein";

/** Camera target in the 1000x430 illustration space. */
export type Focus = { x: number; y: number; zoom: number };

export const ILLUSTRATION_IDS: IllustrationId[] = [
  "solar-cell",
  "solar-home",
  "heart",
  "immune-response",
  "mrna-protein",
];

/* ──────────────────────────────────────────────────────────────
   Shared helpers
   ────────────────────────────────────────────────────────────── */

type Pt = [number, number];

const C = {
  bg: "#0B1220",
  panel: "#17233A",
  teal: "#4FD1C5",
  gold: "#F2B84B",
  red: "#E87979",
  white: "#F4F6FA",
  muted: "#A6B0C2",
  purple: "#A78BFA",
  blue: "#5B9BFF",
  warm: "#FFD98A",
};

const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const ease = Easing.bezier(0.22, 1, 0.36, 1);

const stage = (frame: number, start: number, dur: number): number =>
  interpolate(frame, [start, start + Math.max(1, dur)], [0, 1], { ...CLAMP, easing: ease });

const osc = (t: number, hz: number, amp: number, phase = 0): number =>
  Math.sin(2 * Math.PI * hz * t + phase) * amp;

const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const lerpPt = (a: Pt, b: Pt, p: number): Pt => [lerp(a[0], b[0], p), lerp(a[1], b[1], p)];
const spokes = (n: number) => Array.from({ length: n }, (_, i) => (i * 360) / n);
const rad = (deg: number) => (deg * Math.PI) / 180;

const mix = (c1: string, c2: string, p: number): string => {
  const h = (c: string) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
  const a = h(c1), b = h(c2);
  return `rgb(${a.map((v, i) => Math.round(lerp(v, b[i], p))).join(",")})`;
};

/** Scene duration, so beats can compress when a scene is short. */
const DurCtx = createContext(0);

const useT = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const dur = useContext(DurCtx);
  const k = dur > 0 ? Math.min(1, Math.max(0.5, dur / (fps * 8))) : 1;
  return {
    frame,
    fps,
    t: frame / fps,
    /** seconds → frames, compressed for short scenes (use for beat timing) */
    b: (sec: number) => sec * fps * k,
  };
};

const bez = (a: Pt, c1: Pt, c2: Pt, b: Pt, p: number): Pt => {
  const u = 1 - p;
  return [
    u * u * u * a[0] + 3 * u * u * p * c1[0] + 3 * u * p * p * c2[0] + p * p * p * b[0],
    u * u * u * a[1] + 3 * u * u * p * c1[1] + 3 * u * p * p * c2[1] + p * p * p * b[1],
  ];
};
const bezD = (a: Pt, c1: Pt, c2: Pt, b: Pt) =>
  `M${a[0]} ${a[1]} C${c1[0]} ${c1[1]} ${c2[0]} ${c2[1]} ${b[0]} ${b[1]}`;

const polyAt = (pts: Pt[], p: number): Pt => {
  const lens = pts.slice(1).map((q, i) => Math.hypot(q[0] - pts[i][0], q[1] - pts[i][1]));
  const total = lens.reduce((a, c) => a + c, 0);
  let d = (((p % 1) + 1) % 1) * total;
  for (let i = 0; i < lens.length; i++) {
    if (d <= lens[i]) return lerpPt(pts[i], pts[i + 1], lens[i] ? d / lens[i] : 0);
    d -= lens[i];
  }
  return pts[pts.length - 1];
};
const polyD = (pts: Pt[]) => pts.map((p, i) => `${i ? "L" : "M"}${p[0]} ${p[1]}`).join(" ");

/** Wobbling organic outline centred on 0,0. */
const blobPath = (R: number, t: number, amp = 0.06, seed = 0): string => {
  const n = 44;
  let d = "";
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const r = R * (1 + amp * Math.sin(3 * a + t * 1.3 + seed) + amp * 0.6 * Math.sin(5 * a - t * 1.7 + seed * 2));
    d += `${i ? "L" : "M"}${(Math.cos(a) * r).toFixed(1)} ${(Math.sin(a) * r).toFixed(1)} `;
  }
  return `${d}Z`;
};

/* ──────────────────────────────────────────────────────────────
   Shared primitives
   ────────────────────────────────────────────────────────────── */

/** A path that draws itself on. */
const Draw: React.FC<{
  d: string; color: string; start: number; dur: number; width?: number; opacity?: number;
}> = ({ d, color, start, dur, width = 4, opacity = 1 }) => {
  const { frame } = useT();
  const p = stage(frame, start, dur);
  return (
    <path d={d} fill="none" stroke={color} strokeWidth={width} strokeLinecap="round"
      strokeLinejoin="round" strokeOpacity={opacity} pathLength={1}
      strokeDasharray="1 1" strokeDashoffset={1 - p} opacity={p > 0 ? 1 : 0} />
  );
};

/** Glowing particles travelling along any path function. */
const Particles: React.FC<{
  at: (p: number) => Pt;
  count: number;
  speed: number;
  color: string | ((p: number) => string);
  start: number;
  r?: number;
}> = ({ at, count, speed, color, start, r = 5.5 }) => {
  const { frame, fps } = useT();
  const live = stage(frame, start, 10);
  if (live <= 0) return null;
  const tt = Math.max(0, frame - start) / fps;
  return (
    <>
      {Array.from({ length: count }, (_, i) => {
        const p = (((tt * speed + i / count) % 1) + 1) % 1;
        const [x, y] = at(p);
        const col = typeof color === "string" ? color : color(p);
        const o = Math.min(1, p * 8, (1 - p) * 8) * live;
        return (
          <g key={i} opacity={o}>
            <circle cx={x} cy={y} r={r * 2.3} fill={col} fillOpacity=".18" />
            <circle cx={x} cy={y} r={r} fill={col} />
          </g>
        );
      })}
    </>
  );
};

/** Text label, optionally with a leader line to a target point. */
const Tag: React.FC<{
  x: number; y: number; text: string; at: number;
  color?: string; anchor?: "start" | "middle" | "end"; size?: number;
  leader?: Pt; out?: number;
}> = ({ x, y, text, at, color = C.muted, anchor = "middle", size = 17, leader, out }) => {
  const { frame, t, b } = useT();
  const p = stage(frame, at, b(0.45));
  const o = (out === undefined ? 1 : 1 - stage(frame, out, b(0.4))) * p;
  return (
    <g opacity={o}>
      {leader && (
        <>
          <path d={`M${x} ${y - size * 0.35} L${leader[0]} ${leader[1]}`} stroke={color}
            strokeWidth="2" strokeOpacity=".7" pathLength={1} strokeDasharray="1 1"
            strokeDashoffset={1 - p} />
          <circle cx={leader[0]} cy={leader[1]} r={4 + osc(t, 1, 1.5)} fill={color} />
        </>
      )}
      <text x={x} y={y} textAnchor={anchor} fill={color} fontSize={size} letterSpacing="2"
        transform={`translate(0 ${(1 - p) * 6})`}>
        {text}
      </text>
    </g>
  );
};

const Pulse: React.FC<{ x: number; y: number; color: string; r0?: number; r1?: number; hz?: number }> = ({
  x, y, color, r0 = 10, r1 = 40, hz = 0.8,
}) => {
  const { t } = useT();
  const p = (((t * hz) % 1) + 1) % 1;
  return <circle cx={x} cy={y} r={r0 + (r1 - r0) * p} fill="none" stroke={color}
    strokeWidth="3" opacity={(1 - p) * 0.7} />;
};

const Sun: React.FC<{ x: number; y: number; r?: number; appear: number }> = ({ x, y, r = 24, appear }) => {
  const { t } = useT();
  return (
    <g transform={`translate(${x} ${y}) scale(${appear})`} opacity={appear}>
      <circle r={r * 1.9} fill={C.gold} fillOpacity={0.08 + 0.03 * Math.sin(t * 2)} />
      <circle r={r} fill={C.gold} />
      <g transform={`rotate(${t * 20})`}>
        {spokes(12).map((a) => (
          <path key={a} d={`M0 ${-r * 1.25} V${-r * 1.6}`} transform={`rotate(${a})`}
            stroke={C.gold} strokeWidth="5" strokeLinecap="round" />
        ))}
      </g>
    </g>
  );
};

/* ──────────────────────────────────────────────────────────────
   1. SOLAR CELL — photons free electrons at the p-n junction,
      current flows round a circuit and lights a bulb
   ────────────────────────────────────────────────────────────── */

const SolarCell: React.FC = () => {
  const { frame, fps, t, b } = useT();
  const layers = stage(frame, 0, b(0.8));
  const sunIn = stage(frame, b(0.4), b(0.7));
  const photonsAt = b(1.4);
  const circuitAt = b(2.6);
  const photonsOn = stage(frame, photonsAt, b(0.5));
  const glow = stage(frame, circuitAt + b(0.8), b(1.2));

  const sun: Pt = [130, 80];
  const targets = [380, 450, 520, 590];
  const loop: Pt[] = [[330, 262], [330, 150], [780, 150], [780, 331], [330, 331], [330, 262]];

  return (
    <>
      {/* silicon layers */}
      <g opacity={layers} transform={`translate(0 ${(1 - layers) * 24})`}>
        <rect x="250" y="215" width="400" height="47" rx="5" fill={C.teal} fillOpacity=".2" stroke={C.teal} strokeWidth="3" />
        <rect x="250" y="262" width="400" height="66" rx="5" fill={C.purple} fillOpacity=".2" stroke={C.purple} strokeWidth="3" />
        {[230, 246].map((y) => Array.from({ length: 16 }, (_, i) => (
          <circle key={`n${y}-${i}`} cx={262 + i * 24} cy={y} r="2.5" fill={C.teal} fillOpacity=".3" />
        )))}
        {[280, 296, 312].map((y) => Array.from({ length: 16 }, (_, i) => (
          <circle key={`p${y}-${i}`} cx={262 + i * 24} cy={y} r="2.5" fill={C.purple} fillOpacity=".3" />
        )))}
        <path d="M250 262 H650" stroke={C.gold} strokeWidth="3" strokeDasharray="8 8"
          strokeDashoffset={-t * 20} opacity={0.55 + 0.3 * Math.sin(t * 3)} />
        {[330, 410, 490, 570].map((x) => (
          <rect key={x} x={x - 5} y="203" width="10" height="12" fill={C.gold} />
        ))}
        <path d="M325 203 H575" stroke={C.gold} strokeWidth="4" />
        <rect x="250" y="328" width="400" height="8" rx="3" fill={C.gold} />
      </g>

      <Sun x={sun[0]} y={sun[1]} appear={sunIn} />

      {/* photons */}
      {targets.map((tx, i) => {
        const p = ((((frame - photonsAt) / fps) * 0.42 + i * 0.25) % 1 + 1) % 1;
        const from: Pt = [sun[0] + 22, sun[1] + 14];
        const to: Pt = [tx, 262];
        const base = lerpPt(from, to, p);
        const dx = to[0] - from[0], dy = to[1] - from[1];
        const len = Math.hypot(dx, dy);
        const w = Math.sin(p * Math.PI * 10) * 5;
        const x = base[0] + (-dy / len) * w;
        const y = base[1] + (dx / len) * w;
        const hit = Math.max(0, (p - 0.9) / 0.1);
        return (
          <g key={tx} opacity={photonsOn}>
            <circle cx={x} cy={y} r="11" fill={C.gold} opacity={p < 0.97 ? 0.2 : 0} />
            <circle cx={x} cy={y} r="5.5" fill={C.gold} opacity={p < 0.97 ? 1 : 0} />
            {hit > 0 && <circle cx={to[0]} cy={to[1]} r={6 + hit * 26} fill="none"
              stroke={C.gold} strokeWidth="3" opacity={1 - hit} />}
          </g>
        );
      })}

      {/* holes drifting down */}
      {[0, 1, 2].map((i) => {
        const p = (t * 0.22 + i / 3) % 1;
        const hx = 390 + i * 95, hy = 268 + p * 52;
        return (
          <g key={i} opacity={stage(frame, circuitAt, b(0.5)) * Math.min(1, p * 6, (1 - p) * 6)}>
            <circle cx={hx} cy={hy} r="7" fill="none" stroke={C.purple} strokeWidth="2.5" />
            <path d={`M${hx - 3.5} ${hy}H${hx + 3.5}M${hx} ${hy - 3.5}V${hy + 3.5}`} stroke={C.purple} strokeWidth="2" />
          </g>
        );
      })}

      {/* external circuit */}
      <Draw d={polyD(loop)} color={C.muted} start={circuitAt - b(0.4)} dur={b(1.4)} width={5} opacity={0.7} />

      {/* bulb */}
      <g transform="translate(780 240)">
        <circle r={30 + glow * 34} fill={C.warm} opacity={0.14 * glow} />
        <circle r="28" fill={C.bg} stroke={C.muted} strokeWidth="3" />
        <circle r="28" fill={C.warm} opacity={0.15 + 0.8 * glow} />
        <path d="M-8 14 V0 Q-8 -10 0 -6 Q8 -10 8 0 V14" fill="none"
          stroke={glow > 0.3 ? C.white : C.muted} strokeWidth="3" strokeLinecap="round" />
      </g>

      <Particles at={(p) => polyAt(loop, p)} count={8} speed={0.13} color={C.gold} start={circuitAt} />

      <Tag x={238} y={232} text="N-TYPE SILICON" color={C.teal} anchor="end" size={16} at={b(0.6)} />
      <Tag x={238} y={267} text="P-N JUNCTION" color={C.gold} anchor="end" size={16} at={b(0.9)} />
      <Tag x={238} y={305} text="P-TYPE SILICON" color={C.purple} anchor="end" size={16} at={b(1.2)} />
      <Tag x={130} y={128} text="SUNLIGHT" color={C.gold} at={b(1.0)} />
      <Tag x={555} y={136} text="ELECTRON FLOW" color={C.gold} at={circuitAt + b(0.4)} />
      <Tag x={830} y={246} text="LOAD" color={C.warm} anchor="start" at={circuitAt + b(0.8)} />
    </>
  );
};

/* ──────────────────────────────────────────────────────────────
   2. SOLAR HOME — sun → roof panel → inverter (DC→AC) → house
   ────────────────────────────────────────────────────────────── */

const SolarHome: React.FC = () => {
  const { frame, t, b } = useT();
  const house = stage(frame, 0, b(0.8));
  const sunIn = stage(frame, b(0.4), b(0.7));
  const beamsAt = b(1.2), dcAt = b(2.0), acAt = b(3.4), lightAt = b(4.2);
  const beams = stage(frame, beamsAt, b(0.6));
  const lights = stage(frame, lightAt, b(1.0));
  const morph = stage(frame, acAt - b(0.6), b(1.0));

  const dcWire: Pt[] = [[622, 230], [520, 230], [520, 242]];
  const acWire: Pt[] = [[555, 300], [640, 300]];
  const beamTargets: Pt[] = [[642, 203], [667, 186], [692, 169], [716, 152]];

  const wave = Array.from({ length: 26 }, (_, i) => {
    const x = -24 + i * 1.92;
    const y = (1 - morph) * -6 + morph * Math.sin(x * 0.33 + t * 6) * 9;
    return `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(" ");

  return (
    <>
      <path d="M40 340 H960" stroke={C.muted} strokeOpacity=".4" strokeWidth="3" strokeLinecap="round" />

      <Sun x={130} y={85} appear={sunIn} />

      {/* house */}
      <g opacity={house} transform={`translate(0 ${(1 - house) * 18})`}>
        <path d="M620 232 L740 150 L860 232 Z" fill={C.panel} stroke={C.teal} strokeWidth="4" strokeLinejoin="round" />
        <rect x="640" y="232" width="200" height="108" fill={C.panel} stroke={C.teal} strokeWidth="4" />
        {[665, 775].map((x) => (
          <g key={x}>
            <rect x={x - 6} y="256" width="52" height="52" rx="6" fill={C.warm} fillOpacity={0.12 * lights} />
            <rect x={x} y="262" width="40" height="40" rx="3" fill={C.warm}
              fillOpacity={0.08 + 0.85 * lights} stroke={C.gold} strokeWidth="3" />
          </g>
        ))}
        <rect x="722" y="284" width="36" height="56" fill="#123442" stroke={C.teal} strokeWidth="3" />
      </g>

      {/* roof panel */}
      <g transform="translate(686 187) rotate(-34.35)" opacity={house}>
        <rect x="-58" y="-20" width="116" height="16" rx="2" fill="#164653" stroke={C.gold} strokeWidth="3" />
        <path d="M-29 -20 V-4 M0 -20 V-4 M29 -20 V-4 M-58 -12 H58" stroke={C.gold} strokeWidth="1.5" />
        <rect x={-58 + ((t * 0.5) % 1) * 104} y="-20" width="12" height="16" fill={C.white}
          opacity={0.35 * beams} transform="skewX(-20)" />
      </g>

      {/* sun beams */}
      {beamTargets.map((to, i) => (
        <path key={i} d={`M152 96 L${to[0]} ${to[1]}`} stroke={C.gold} strokeWidth="3"
          strokeDasharray="12 10" strokeDashoffset={-t * 50} opacity={0.6 * beams} strokeLinecap="round" />
      ))}

      {/* inverter */}
      <g opacity={stage(frame, b(1.0), b(0.7))}>
        <rect x="485" y="242" width="70" height="90" rx="10" fill={C.panel} stroke={C.gold} strokeWidth="4" />
        <rect x="495" y="254" width="50" height="30" rx="3" fill={C.bg} stroke={C.teal} strokeWidth="2" />
        <g transform="translate(520 269)">
          <path d={wave} fill="none" stroke={mix(C.teal, C.gold, morph)} strokeWidth="3" strokeLinecap="round" />
        </g>
        <circle cx="520" cy="312" r="6" fill={frame > acAt ? C.teal : C.muted} opacity={0.6 + 0.4 * Math.sin(t * 5)} />
      </g>

      <Draw d={polyD(dcWire)} color={C.teal} start={dcAt - b(0.4)} dur={b(0.8)} width={5} opacity={0.6} />
      <Draw d={polyD(acWire)} color={C.gold} start={acAt - b(0.3)} dur={b(0.6)} width={5} opacity={0.6} />
      <Particles at={(p) => polyAt(dcWire, p)} count={5} speed={0.6} color={C.teal} start={dcAt} r={4.5} />
      <Particles at={(p) => polyAt(acWire, p)} count={4} speed={0.7} color={C.gold} start={acAt} r={4.5} />

      <Tag x={130} y={132} text="SUNLIGHT" color={C.gold} at={b(0.9)} />
      <Tag x={590} y={166} text="SOLAR PANELS" color={C.gold} anchor="end" at={b(1.4)} leader={[664, 188]} />
      <Tag x={571} y={218} text="DC" color={C.teal} size={15} at={dcAt} />
      <Tag x={598} y={290} text="AC" color={C.gold} size={15} at={acAt} />
      <Tag x={520} y={366} text="INVERTER" color={C.gold} at={b(1.6)} />
      <Tag x={740} y={372} text="YOUR HOME" color={C.teal} at={b(1.0)} />
    </>
  );
};

/* ──────────────────────────────────────────────────────────────
   3. HEART — beating heart with valves, blood colour changes
      (blue = oxygen-poor, red = oxygen-rich)
   ────────────────────────────────────────────────────────────── */

const Chamber: React.FC<{
  cx: number; cy: number; rx: number; ry: number; color: string; squeeze: number; label: string;
}> = ({ cx, cy, rx, ry, color, squeeze, label }) => (
  <g transform={`translate(${cx} ${cy}) scale(${1 - squeeze})`}>
    <ellipse rx={rx} ry={ry} fill={color} fillOpacity=".22" stroke={color} strokeWidth="4" />
    <text textAnchor="middle" y="7" fontSize="22" fontWeight="700" fill={C.white} fillOpacity=".75">{label}</text>
  </g>
);

const Valve: React.FC<{ x: number; y: number; open: number }> = ({ x, y, open }) => {
  const a = rad(10 + 55 * open), L = 18;
  return (
    <g stroke={C.white} strokeWidth="4" strokeLinecap="round" opacity=".85">
      <path d={`M${x - 20} ${y} L${x - 20 + L * Math.cos(a)} ${y + L * Math.sin(a)}`} />
      <path d={`M${x + 20} ${y} L${x + 20 - L * Math.cos(a)} ${y + L * Math.sin(a)}`} />
    </g>
  );
};

type StreamDef = {
  a: Pt; c1: Pt; c2: Pt; b: Pt;
  color: string | ((p: number) => string);
  start: number; count?: number; speed?: number;
};

const Heart: React.FC = () => {
  const { frame, t, b } = useT();
  const hp = (t * 1.2) % 1; // 72 bpm
  const bump = (c: number, w: number) => Math.exp(-Math.pow((hp - c) / w, 2));
  const atria = bump(0.08, 0.05);
  const vent = bump(0.24, 0.07) + 0.5 * bump(0.44, 0.06);
  const open = 1 - Math.min(1, vent * 1.4);
  const sc = 1 + 0.01 * atria + 0.028 * vent;
  const hIn = stage(frame, 0, b(0.8));

  const streams: StreamDef[] = [
    { a: [190, 252], c1: [290, 252], c2: [300, 180], b: [398, 180], color: C.blue, start: b(1.0) },
    { a: [444, 198], c1: [440, 215], c2: [444, 228], b: [448, 250], color: C.blue, start: b(1.4), count: 3 },
    { a: [478, 222], c1: [500, 185], c2: [470, 140], b: [440, 104], color: C.blue, start: b(1.8) },
    { a: [590, 104], c1: [605, 125], c2: [590, 130], b: [570, 150], color: C.red, start: b(2.2), count: 3 },
    { a: [560, 200], c1: [562, 225], c2: [562, 240], b: [562, 262], color: C.red, start: b(2.6), count: 3 },
    { a: [590, 225], c1: [640, 180], c2: [640, 120], b: [700, 136], color: C.red, start: b(3.0), count: 4 },
    { a: [700, 136], c1: [770, 150], c2: [800, 200], b: [830, 245], color: C.red, start: b(3.3), count: 4 },
    { a: [850, 285], c1: [800, 400], c2: [200, 400], b: [150, 285],
      color: (p) => mix(C.red, C.blue, Math.min(1, p * 1.4)), start: b(3.6), count: 10, speed: 0.16 },
  ];

  return (
    <>
      {/* lungs */}
      <g opacity={stage(frame, b(0.3), b(0.8))}>
        {[430, 575].map((x) => (
          <g key={x}>
            <ellipse cx={x} cy="66" rx="56" ry="38" fill={C.teal} fillOpacity=".12" stroke={C.teal} strokeWidth="3" />
            <path d={`M${x} 100 V66 M${x} 80 L${x - 20} 62 M${x} 80 L${x + 20} 58`}
              stroke={C.teal} strokeOpacity=".5" strokeWidth="3" strokeLinecap="round" fill="none" />
            <text x={x + 24} y={50 + osc(t, 0.5, 3, x)} fontSize="13" fill={C.teal} opacity=".7">O2</text>
          </g>
        ))}
      </g>

      {/* body */}
      {[150, 850].map((x) => (
        <g key={x} opacity={stage(frame, b(0.4), b(0.8))}>
          <ellipse cx={x} cy="262" rx="42" ry="36" fill={C.gold} fillOpacity=".12" stroke={C.gold} strokeWidth="3" />
          <text x={x} y="268" textAnchor="middle" fontSize="16" fill={C.gold} letterSpacing="2">BODY</text>
        </g>
      ))}

      {/* vessel tubes */}
      {streams.map((s, i) => (
        <React.Fragment key={i}>
          <Draw d={bezD(s.a, s.c1, s.c2, s.b)} color={C.muted} start={s.start} dur={b(0.6)} width={14} opacity={0.14} />
          <Draw d={bezD(s.a, s.c1, s.c2, s.b)} color={C.muted} start={s.start} dur={b(0.6)} width={3} opacity={0.5} />
        </React.Fragment>
      ))}

      {/* the beating heart */}
      <g opacity={hIn} transform={`translate(505 240) scale(${sc}) translate(-505 -240)`}>
        <Chamber cx={445} cy={185} rx={50} ry={44} color={C.blue} squeeze={0.07 * atria} label="RA" />
        <Chamber cx={560} cy={185} rx={50} ry={44} color={C.red} squeeze={0.07 * atria} label="LA" />
        <Chamber cx={448} cy={270} rx={52} ry={62} color={C.blue} squeeze={0.06 * vent} label="RV" />
        <Chamber cx={562} cy={275} rx={58} ry={70} color={C.red} squeeze={0.06 * vent} label="LV" />
        <path d="M503 148 V340" stroke={C.muted} strokeOpacity=".4" strokeWidth="3" />
        <Valve x={448} y={230} open={open} />
        <Valve x={562} y={230} open={open} />
      </g>

      {/* blood */}
      {streams.map((s, i) => (
        <Particles key={i} at={(p) => bez(s.a, s.c1, s.c2, s.b, p)} count={s.count ?? 5}
          speed={s.speed ?? 0.35} color={s.color} start={s.start + b(0.5)} />
      ))}

      <Tag x={500} y={20} text="LUNGS" color={C.teal} at={b(0.9)} />
      <Tag x={240} y={236} text="VENAE CAVAE" color={C.blue} size={15} at={b(1.1)} />
      <Tag x={380} y={126} text="PULMONARY ARTERY" color={C.blue} size={15} anchor="end" at={b(1.9)} leader={[466, 138]} />
      <Tag x={645} y={118} text="PULMONARY VEINS" color={C.red} size={15} anchor="start" at={b(2.3)} leader={[593, 127]} />
      <Tag x={700} y={112} text="AORTA" color={C.red} size={15} at={b(3.1)} leader={[700, 136]} />

      <g opacity={stage(frame, b(1.0), b(0.6))}>
        <circle cx="70" cy="406" r="6" fill={C.blue} />
        <text x="84" y="411" fontSize="14" fill={C.muted} letterSpacing="2">OXYGEN-POOR</text>
        <circle cx="830" cy="406" r="6" fill={C.red} />
        <text x="844" y="411" fontSize="14" fill={C.muted} letterSpacing="2">OXYGEN-RICH</text>
      </g>
    </>
  );
};

/* ──────────────────────────────────────────────────────────────
   4. IMMUNE RESPONSE — antibodies bind a pathogen, a phagocyte
      engulfs it, memory cells are left behind
   ────────────────────────────────────────────────────────────── */

const AntibodyY: React.FC = () => (
  <path d="M0 0 V-14 M0 -14 L-9 -28 M0 -14 L9 -28" fill="none" stroke={C.teal}
    strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
);

const ImmuneResponse: React.FC = () => {
  const { frame, t, b } = useT();
  const enter = stage(frame, 0, b(1.0));
  const macIn = stage(frame, b(2.0), b(1.5));
  const engulf = stage(frame, b(3.9), b(1.4));
  const flash = stage(frame, b(5.0), b(0.8));
  const memAt = b(5.4);

  const M: Pt = [lerp(40, 340, macIn), 215 + osc(t, 0.25, 6)];
  const P0: Pt = [lerp(900, 650, enter), 215 + osc(t, 0.3, 8)];
  const P = lerpPt(P0, [M[0] + 28, M[1] + 14], engulf);
  const sc = 1 - 0.62 * engulf;
  const rot = t * 14;
  const tipR = 70;

  return (
    <>
      {/* macrophage */}
      <g transform={`translate(${M[0]} ${M[1]})`} opacity={macIn}>
        <path d={blobPath(100, t, 0.06)} fill={C.purple} fillOpacity=".14" stroke={C.purple} strokeWidth="4" strokeLinejoin="round" />
        <g transform="translate(-30 -22)">
          <path d={blobPath(34, t, 0.05, 2)} fill={C.purple} fillOpacity=".35" />
        </g>
        {Array.from({ length: 6 }, (_, i) => (
          <circle key={i} cx={Math.cos(rad(i * 60 + t * 10)) * 64} cy={Math.sin(rad(i * 60 + t * 10)) * 64}
            r="5" fill={C.purple} fillOpacity=".6" />
        ))}
        {engulf > 0 && (
          <circle cx={P[0] - M[0]} cy={P[1] - M[1]} r={(tipR + 8) * sc} fill="none" stroke={C.gold}
            strokeWidth="3" strokeDasharray="6 6" opacity={engulf * (1 - flash)} />
        )}
        {flash > 0 && flash < 1 && (
          <circle r={100 + flash * 50} fill="none" stroke={C.gold} strokeWidth="4" opacity={1 - flash} />
        )}
      </g>

      {/* pathogen */}
      <g transform={`translate(${P[0]} ${P[1]}) scale(${sc}) rotate(${rot})`} opacity={enter * (1 - flash)}>
        {spokes(8).map((a) => (
          <g key={a} transform={`rotate(${a})`}>
            <path d="M0 -50 V-64" stroke={C.red} strokeWidth="7" strokeLinecap="round" />
            <circle cy="-70" r="7" fill={C.red} />
          </g>
        ))}
        <circle r="50" fill="#743B50" stroke={C.red} strokeWidth="3" />
        <circle cx="-14" cy="-9" r="8" fill="#F7B7B7" />
        <circle cx="15" cy="13" r="7" fill="#F7B7B7" />
        <circle cx="13" cy="-18" r="5" fill="#F7B7B7" />
      </g>

      {/* antibodies fly in and bind each spike */}
      {Array.from({ length: 8 }, (_, i) => {
        const q = stage(frame, b(0.9) + i * b(0.14), b(0.9));
        const th = i * 45 + rot;
        const att: Pt = [P[0] + Math.cos(rad(th)) * (tipR + 28) * sc, P[1] + Math.sin(rad(th)) * (tipR + 28) * sc];
        const start: Pt = [120 + i * 25, i % 2 ? 70 : 360];
        const pos = lerpPt(start, att, q);
        const arc = -Math.sin(q * Math.PI) * 40;
        const vis = stage(frame, b(0.8) + i * b(0.14), b(0.2)) * (1 - flash);
        return (
          <g key={i} opacity={vis}
            transform={`translate(${pos[0]} ${pos[1] + arc}) rotate(${th - 90 + (1 - q) * 220}) scale(${sc * (0.7 + 0.3 * q)})`}>
            <AntibodyY />
          </g>
        );
      })}

      {/* memory cells */}
      {[0, 1, 2].map((i) => {
        const q = stage(frame, memAt + i * b(0.25), b(1.1));
        const pos = lerpPt([M[0] + 30, M[1]], [640 + i * 90, 150 + (i % 2) * 110], q);
        return (
          <g key={i} opacity={q}
            transform={`translate(${pos[0]} ${pos[1] + osc(t, 0.4, 6, i)}) scale(${0.3 + 0.7 * q})`}>
            <circle r="30" fill={C.teal} fillOpacity=".15" stroke={C.teal} strokeWidth="3" />
            <circle r="12" fill={C.teal} fillOpacity=".4" />
            <path d="M-8 2 L-2 9 L9 -7" fill="none" stroke={C.teal} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        );
      })}

      <Tag x={650} y={335} text="PATHOGEN" color={C.red} at={b(0.5)} out={b(3.8)} />
      <Tag x={650} y={100} text="ANTIBODIES BIND THE ANTIGENS" color={C.teal} at={b(1.4)} out={b(3.8)} />
      <Tag x={340} y={345} text="IMMUNE CELL ENGULFS IT" color={C.purple} at={b(4.0)} />
      <Tag x={730} y={335} text="MEMORY CELLS REMAIN" color={C.gold} at={memAt + b(0.8)} />
    </>
  );
};

/* ──────────────────────────────────────────────────────────────
   5. mRNA → PROTEIN — nanoparticle enters a cell, releases mRNA,
      a ribosome builds a protein, antigens appear on the surface
   ────────────────────────────────────────────────────────────── */

const Mrna: React.FC = () => {
  const { frame, t, b } = useT();
  const cellIn = stage(frame, 0, b(0.9));
  const travel = stage(frame, b(0.7), b(1.8));
  const burst = stage(frame, b(2.5), b(0.6));
  const strandAt = b(2.6);
  const ribP = stage(frame, b(3.6), b(2.6));
  const fold = stage(frame, b(6.3), b(0.7));
  const toMem = stage(frame, b(7.0), b(1.0));
  const antigenAt = b(8.0);
  const imm = stage(frame, antigenAt + b(0.4), b(1.0));

  const C0: Pt = [640, 215];
  const R = 175;
  const lnpX = lerp(90, 525, travel);
  const strand = Array.from({ length: 25 }, (_, i): Pt => [525 + i * 9.8, 262 + Math.sin(i * 0.8) * 8]);
  const rx = 525 + ribP * 230;
  const nBeads = Math.floor(ribP * 9);
  const F: Pt = [690, 140];
  const Q: Pt = [C0[0] + R * Math.cos(rad(-75)), C0[1] + R * Math.sin(rad(-75))];
  const protPos = lerpPt(F, Q, toMem);
  const blobs: [number, number, number][] = [
    [0, 0, 14], [-20, -11, 10], [18, -15, 9], [22, 11, 11], [-15, 18, 10], [0, -29, 7], [-29, 9, 7],
  ];

  return (
    <>
      {/* cell */}
      <g transform={`translate(${C0[0]} ${C0[1]})`} opacity={cellIn}>
        <path d={blobPath(R, t, 0.025, 1)} fill={C.teal} fillOpacity=".06" stroke={C.teal} strokeWidth="5" strokeLinejoin="round" />
      </g>

      {/* lipid nanoparticle */}
      <g transform={`translate(${lnpX} 215) scale(${1 - burst * 0.5})`} opacity={1 - burst}>
        <circle r="34" fill={C.gold} fillOpacity=".15" stroke={C.gold} strokeWidth="4" />
        {spokes(12).map((a) => (
          <circle key={a} cx={Math.cos(rad(a)) * 34} cy={Math.sin(rad(a)) * 34} r="4.5" fill={C.gold} />
        ))}
        <path d="M-14 0 Q-7 -10 0 0 T14 0" fill="none" stroke={C.gold} strokeWidth="3" strokeLinecap="round" />
      </g>
      {burst > 0 && burst < 1 && (
        <circle cx="525" cy="215" r={34 + burst * 46} fill="none" stroke={C.gold} strokeWidth="3" opacity={1 - burst} />
      )}

      {/* mRNA strand */}
      <Draw d={polyD(strand)} color={C.gold} start={strandAt} dur={b(1.0)} width={6} />

      {/* ribosome + growing chain */}
      <g transform={`translate(${rx} 250)`} opacity={stage(frame, b(3.3), b(0.4))}>
        <ellipse cx="0" cy="-8" rx="26" ry="14" fill={C.purple} fillOpacity=".55" stroke={C.purple} strokeWidth="3" />
        <ellipse cx="0" cy="6" rx="19" ry="9" fill={C.purple} fillOpacity=".9" />
      </g>
      {Array.from({ length: nBeads }, (_, i) => {
        const base: Pt = [rx + osc(t, 0.7, 5, i * 0.7), 232 - i * 10];
        const pos = lerpPt(base, F, fold);
        return <circle key={i} cx={pos[0]} cy={pos[1]} r="6" fill={i % 2 ? C.gold : C.teal} opacity={1 - fold} />;
      })}

      {/* folded protein → travels to the surface */}
      <g transform={`translate(${protPos[0]} ${protPos[1]}) scale(${fold * (1 - 0.4 * toMem)})`}
        opacity={fold * (1 - stage(frame, antigenAt - b(0.2), b(0.3)))}>
        {blobs.map(([x, y, r], i) => (
          <circle key={i} cx={x} cy={y} r={r * (1 + osc(t, 0.5, 0.08, i))}
            fill={i % 2 ? C.gold : C.purple} fillOpacity=".85" />
        ))}
      </g>

      {/* antigens displayed on the membrane */}
      {[-100, -75, -50].map((deg, i) => {
        const p = stage(frame, antigenAt + i * b(0.2), b(0.5));
        const bx = C0[0] + (R + 2) * Math.cos(rad(deg));
        const by = C0[1] + (R + 2) * Math.sin(rad(deg));
        return (
          <g key={deg} transform={`translate(${bx} ${by}) rotate(${deg + 90})`} opacity={p}>
            <path d={`M0 0 V${-24 * p}`} stroke={C.teal} strokeWidth="4" strokeLinecap="round" />
            <circle cy={-26 * p} r="9" fill={C.gold} />
          </g>
        );
      })}

      {/* immune cell notices */}
      {(() => {
        const pos = lerpPt([940, 70], [800, 62], imm);
        return (
          <g transform={`translate(${pos[0]} ${pos[1] + osc(t, 0.5, 5)})`} opacity={imm}>
            <circle r="26" fill={C.teal} fillOpacity=".15" stroke={C.teal} strokeWidth="3" />
            <circle r="10" fill={C.teal} fillOpacity=".4" />
          </g>
        );
      })()}

      <Tag x={160} y={290} text="LIPID NANOPARTICLE" color={C.gold} at={b(0.5)} out={b(2.4)} />
      <Tag x={640} y={300} text="mRNA RELEASED" color={C.gold} at={strandAt + b(0.5)} />
      <Tag x={640} y={332} text="RIBOSOME READS THE CODE" color={C.purple} at={b(3.8)} />
      <Tag x={690} y={100} text="NEW PROTEIN" color={C.purple} at={b(6.4)} out={b(7.4)} />
      <Tag x={520} y={62} text="ANTIGEN ON THE SURFACE" color={C.teal} anchor="end" at={antigenAt + b(0.4)} leader={[666, 30]} />
    </>
  );
};

/* ──────────────────────────────────────────────────────────────
   Registry, camera, entry point
   ────────────────────────────────────────────────────────────── */

const REGISTRY: Record<IllustrationId, React.FC> = {
  "solar-cell": SolarCell,
  "solar-home": SolarHome,
  heart: Heart,
  "immune-response": ImmuneResponse,
  "mrna-protein": Mrna,
};

const Camera: React.FC<{ focus?: Focus; children: React.ReactNode }> = ({ focus, children }) => {
  const { frame, b } = useT();
  const k = focus ? stage(frame, b(0.9), b(1.6)) : 0;
  const z = focus ? 1 + (focus.zoom - 1) * k : 1;
  const fx = focus ? 500 + (focus.x - 500) * k : 500;
  const fy = focus ? 215 + (focus.y - 215) * k : 215;
  return <g transform={`translate(500 215) scale(${z}) translate(${-fx} ${-fy})`}>{children}</g>;
};

const Foot: React.FC<{ text?: string }> = ({ text }) => {
  const { frame, b } = useT();
  if (!text) return null;
  const p = stage(frame, b(1.0), b(0.6));
  return <text x="500" y="420" textAnchor="middle" fill={C.muted} fontSize="17" opacity={p}>{text}</text>;
};

/** Render inside an <svg viewBox="0 0 1000 430">. */
export const Illustration: React.FC<{
  id: IllustrationId;
  duration: number;
  focus?: Focus;
  footnote?: string;
}> = ({ id, duration, focus, footnote }) => {
  const Comp = REGISTRY[id];
  return (
    <DurCtx.Provider value={duration}>
      <Camera focus={focus}>
        <Comp />
      </Camera>
      <Foot text={footnote} />
    </DurCtx.Provider>
  );
};

/**
 * Keyword fallback for when the backend didn't send an explicit illustration id.
 * Prefer having the script generator return `{ type: "illustration", id }` itself.
 */
export const pickIllustration = (
  topic: string,
  text: string,
): { id: IllustrationId; focus?: Focus } | null => {
  if (/\b(heart|cardiac|cardio\w*)\b/i.test(topic)) {
    let focus: Focus | undefined;
    if (/ventric/i.test(text)) focus = { x: 505, y: 270, zoom: 1.55 };
    else if (/atri(um|a)/i.test(text)) focus = { x: 505, y: 175, zoom: 1.55 };
    else if (/lung|pulmon/i.test(text)) focus = { x: 500, y: 100, zoom: 1.6 };
    else if (/aort|body|tissue/i.test(text)) focus = { x: 740, y: 190, zoom: 1.5 };
    return { id: "heart", focus };
  }

  if (/\b(solar|photovoltaic|photovoltaics)\b/i.test(topic)) {
    if (/inverter|alternating|\bAC\b|home|house|roof|appliance|outlet|grid/i.test(text)) return { id: "solar-home" };
    if (/electron|photon|silicon|junction|semiconductor|cell|current|circuit|convert/i.test(text)) return { id: "solar-cell" };
    return { id: "solar-home" };
  }

  if (/\b(vaccin\w*|immuni[sz]ation)\b/i.test(topic)) {
    if (/mrna|messenger|instruction|protein|lipid/i.test(text)) return { id: "mrna-protein" };
    return { id: "immune-response" };
  }

  return null;
};