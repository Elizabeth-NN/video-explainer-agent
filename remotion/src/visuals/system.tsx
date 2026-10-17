import React, { useMemo } from "react";
import { z } from "zod";
import { ACCENTS, C, Footnote, Note, arrowPath, clip, osc, stage, useT, useTrace, wrap } from "./kit";
import { balancerTrace, cacheTrace, ringTrace } from "./systems";
import { HINTS } from "./hints";

/* ───────────── infrastructure glyphs (drawn in a ±40 box) ───────────── */

export const INFRA_KINDS = [
  "client", "cdn", "loadbalancer", "server", "service", "cache", "database",
  "queue", "storage", "worker", "dns", "firewall", "monitor",
] as const;
export type InfraKind = (typeof INFRA_KINDS)[number];

const line = (c: string, w = 4) =>
  ({ fill: "none", stroke: c, strokeWidth: w, strokeLinecap: "round", strokeLinejoin: "round" }) as const;

export const GLYPH: Record<InfraKind, React.FC<{ c: string }>> = {
  client: ({ c }) => (
    <g {...line(c)}>
      <rect x="-30" y="-26" width="60" height="40" rx="4" fill={c} fillOpacity=".15" />
      <path d="M-18 28 H18 M0 14 V28" />
    </g>
  ),
  cdn: ({ c }) => (
    <g {...line(c, 3.5)}>
      <circle r="28" fill={c} fillOpacity=".12" />
      <ellipse rx="12" ry="28" />
      <path d="M-28 0 H28 M-24 -14 H24 M-24 14 H24" />
    </g>
  ),
  loadbalancer: ({ c }) => (
    <g {...line(c)}>
      <path d="M-32 0 H-8 M-8 0 L12 -22 H30 M-8 0 H30 M-8 0 L12 22 H30" />
      <circle cx="-32" r="5" fill={c} />
      <circle cx="30" cy="-22" r="5" fill={c} />
      <circle cx="30" r="5" fill={c} />
      <circle cx="30" cy="22" r="5" fill={c} />
    </g>
  ),
  server: ({ c }) => (
    <g {...line(c, 3.5)}>
      {[-30, -9, 12].map((y) => (
        <g key={y}>
          <rect x="-28" y={y} width="56" height="18" rx="4" fill={c} fillOpacity=".15" />
          <circle cx="-17" cy={y + 9} r="2.5" fill={c} />
        </g>
      ))}
    </g>
  ),
  service: ({ c }) => (
    <g {...line(c, 3.5)}>
      <path d="M0 -32 L28 -16 V16 L0 32 L-28 16 V-16 Z" fill={c} fillOpacity=".15" />
      <circle r="8" />
    </g>
  ),
  cache: ({ c }) => (
    <g>
      <rect x="-28" y="-28" width="56" height="56" rx="10" fill={c} fillOpacity=".12" stroke={c} strokeWidth="3.5" />
      <path d="M5 -20 L-13 3 H-1 L-6 20 L13 -4 H1 Z" fill={c} />
    </g>
  ),
  database: ({ c }) => (
    <g {...line(c, 3.5)}>
      <path d="M-26 -22 V22 A26 9 0 0 0 26 22 V-22" fill={c} fillOpacity=".12" />
      <ellipse cy="-22" rx="26" ry="9" fill={c} fillOpacity=".2" />
      <path d="M-26 0 A26 9 0 0 0 26 0" />
    </g>
  ),
  queue: ({ c }) => (
    <g {...line(c, 3.5)}>
      {[-34, -12, 10].map((x) => (
        <rect key={x} x={x} y="-14" width="20" height="28" rx="4" fill={c} fillOpacity=".15" />
      ))}
      <path d="M-30 26 H30 M22 20 L30 26 L22 32" />
    </g>
  ),
  storage: ({ c }) => (
    <g {...line(c, 3.5)}>
      <path d="M-28 -14 L-20 28 H20 L28 -14" fill={c} fillOpacity=".12" />
      <ellipse cy="-14" rx="28" ry="8" fill={c} fillOpacity=".2" />
    </g>
  ),
  worker: ({ c }) => (
    <g>
      {Array.from({ length: 8 }, (_, i) => (
        <rect key={i} x="-5" y="-32" width="10" height="13" rx="2" fill={c} transform={`rotate(${i * 45})`} />
      ))}
      <circle r="21" fill="none" stroke={c} strokeWidth="6" />
      <circle r="6" fill={c} />
    </g>
  ),
  dns: ({ c }) => (
    <text textAnchor="middle" y="9" fill={c} fontSize="26" fontWeight="800" letterSpacing="1">DNS</text>
  ),
  firewall: ({ c }) => (
    <g {...line(c, 3)}>
      <rect x="-30" y="-26" width="60" height="52" rx="4" fill={c} fillOpacity=".12" />
      <path d="M-30 -9 H30 M-30 9 H30 M0 -26 V-9 M-15 -9 V9 M15 -9 V9 M0 9 V26" />
    </g>
  ),
  monitor: ({ c }) => (
    <g {...line(c, 3.5)}>
      <rect x="-30" y="-26" width="60" height="52" rx="6" fill={c} fillOpacity=".12" />
      <path d="M-20 10 L-8 -4 L2 4 L18 -14" />
    </g>
  ),
};

/* ───────────── architecture ───────────── */

export const architectureSchema = z.object({
  type: z.literal("architecture"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  nodes: z
    .array(
      z.object({
        id: z.string().min(1),
        label: z.string(),
        kind: z.enum(INFRA_KINDS).catch("service"),
        tier: z.number().int().min(0).max(5).optional(),
      }),
    )
    .min(2)
    .max(10),
  links: z.array(z.object({ from: z.string(), to: z.string(), label: z.string().optional() })).min(1).max(14),
  path: z.array(z.string()).max(8).optional(),
});
export type ArchitectureSpec = z.infer<typeof architectureSchema>;

/** Explicit tiers win; otherwise a node sits one column right of its deepest source. */
const layoutTiers = (spec: ArchitectureSpec): Map<string, number> => {
  const ids = spec.nodes.map((n) => n.id);
  const depth = new Map<string, number>(ids.map((id) => [id, 0]));
  for (let pass = 0; pass < ids.length; pass++) {
    for (const l of spec.links) {
      if (!depth.has(l.from) || !depth.has(l.to)) continue;
      if (depth.get(l.to)! < depth.get(l.from)! + 1 && depth.get(l.from)! + 1 < ids.length) {
        depth.set(l.to, depth.get(l.from)! + 1);
      }
    }
  }
  spec.nodes.forEach((n) => n.tier !== undefined && depth.set(n.id, n.tier));
  const ranks = [...new Set(depth.values())].sort((a, b) => a - b);
  return new Map(ids.map((id) => [id, ranks.indexOf(depth.get(id)!)]));
};

export const ArchitectureDiagram: React.FC<{ spec: ArchitectureSpec; duration: number }> = ({ spec, duration }) => {
  const { frame, t, s } = useT();
  const tiers = useMemo(() => layoutTiers(spec), [spec]);
  const cols = Math.max(...tiers.values()) + 1;
  const pos = useMemo(() => {
    const byTier = new Map<number, string[]>();
    spec.nodes.forEach((n) => byTier.set(tiers.get(n.id)!, [...(byTier.get(tiers.get(n.id)!) ?? []), n.id]));
    const out = new Map<string, { x: number; y: number; r: number }>();
    byTier.forEach((members, tier) => {
      const m = members.length;
      const gap = Math.min(105, 280 / Math.max(1, m - 1));
      members.forEach((id, j) =>
        out.set(id, {
          x: cols === 1 ? 500 : 110 + (tier * 780) / (cols - 1),
          y: 190 + (j - (m - 1) / 2) * gap,
          r: m > 4 ? 24 : 30,
        }),
      );
    });
    return out;
  }, [spec, tiers, cols]);

  const path = (spec.path ?? []).filter((id) => pos.has(id));
  const segs = path.slice(0, -1).map((a, i) => ({ a, b: path[i + 1] }));
  const { frame: seg, index, progress } = useTrace(segs.length ? segs : [{ a: "", b: "" }], duration);
  const live = segs.length > 0;
  const hotLinks = new Set(segs.slice(0, index + 1).map((x) => `${x.a}>${x.b}`));
  const labelOf = (id: string) => spec.nodes.find((n) => n.id === id)?.label ?? id;

  return (
    <>
      {spec.links.map((l, i) => {
        const a = pos.get(l.from), b = pos.get(l.to);
        if (!a || !b) return null;
        const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
        const ux = dx / len, uy = dy / len;
        const hot = live && hotLinks.has(`${l.from}>${l.to}`);
        const col = hot ? C.gold : C.muted;
        const x2 = b.x - ux * (b.r + 8), y2 = b.y - uy * (b.r + 8);
        const p = stage(frame, s(0.5) + i * s(0.1), s(0.4));
        return (
          <g key={i} opacity={p * (hot ? 1 : 0.6)}>
            <line x1={a.x + ux * (a.r + 6)} y1={a.y + uy * (a.r + 6)} x2={x2} y2={y2} stroke={col}
              strokeWidth={hot ? 4 : 3} strokeLinecap="round" />
            <path d={arrowPath(x2, y2, ux, uy)} fill="none" stroke={col} strokeWidth="3"
              strokeLinecap="round" strokeLinejoin="round" />
            {l.label && (
              <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 8} textAnchor="middle" fill={C.white}
                fontSize="13" stroke={C.bg} strokeWidth="5" paintOrder="stroke">{clip(l.label, 14)}</text>
            )}
          </g>
        );
      })}
      {spec.nodes.map((n, i) => {
        const p0 = pos.get(n.id)!;
        const p = stage(frame, s(0.1) + i * s(0.08), s(0.4));
        const target = live && seg.b === n.id;
        const col = target ? C.gold : C.teal;
        const Glyph = GLYPH[n.kind];
        return (
          <g key={n.id} transform={`translate(${p0.x} ${p0.y + osc(t, 0.3, 3, i)}) scale(${0.8 + 0.2 * p})`} opacity={p}>
            <circle r={p0.r + 6} fill={col} fillOpacity=".08" />
            <circle r={p0.r} fill={C.panel} stroke={col} strokeWidth="3" />
            <g transform={`scale(${p0.r / 46})`}><Glyph c={col} /></g>
            {wrap(n.label, 13, 2).map((ln, k) => (
              <text key={k} y={p0.r + 22 + k * 17} textAnchor="middle" fill={col} fontSize="15" fontWeight="700">{ln}</text>
            ))}
          </g>
        );
      })}
      {live && (() => {
        const a = pos.get(seg.a), b = pos.get(seg.b);
        if (!a || !b) return null;
        const e = progress < 0.5 ? 2 * progress * progress : 1 - Math.pow(-2 * progress + 2, 2) / 2;
        return <circle cx={a.x + (b.x - a.x) * e} cy={a.y + (b.y - a.y) * e} r="8" fill={C.gold} />;
      })()}
      {live && <Note text={`${labelOf(seg.a)} → ${labelOf(seg.b)}`} />}
      <Footnote text={spec.footnote} at={s(1.2)} />
    </>
  );
};

export const architectureVisual = {
  type: "architecture" as const, schema: architectureSchema, Component: ArchitectureDiagram, plannerHint: HINTS.architecture,
};

/* ───────────── load balancer ───────────── */

export const balancerSchema = z.object({
  type: z.literal("balancer"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  servers: z.number().int().min(2).max(5),
  requests: z.number().int().min(3).max(12),
  algorithm: z.enum(["round-robin", "least-connections", "ip-hash", "weighted-round-robin"]).catch("round-robin"),
  weights: z.array(z.number()).max(5).optional(),
  costs: z.array(z.number().int().min(1).max(5)).max(12).optional(),
});
export type BalancerSpec = z.infer<typeof balancerSchema>;

export const BalancerDiagram: React.FC<{ spec: BalancerSpec; duration: number }> = ({ spec, duration }) => {
  const { s } = useT();
  const frames = useMemo(
    () => balancerTrace(spec.servers, spec.requests, spec.algorithm, spec.weights, spec.costs),
    [spec],
  );
  const { frame: fr, progress } = useTrace(frames, duration);
  const n = spec.servers;
  const h = Math.min(64, 310 / n - 12);
  const ys = Array.from({ length: n }, (_, i) => 190 + (i - (n - 1) / 2) * (h + 12));
  const lb = { x: 190, y: 190 };
  const LB = GLYPH.loadbalancer;

  return (
    <>
      <text x="500" y="30" textAnchor="middle" fill={C.muted} fontSize="16" fontWeight="700" letterSpacing="3">
        {spec.algorithm.replace(/-/g, " ").toUpperCase()}
      </text>
      {ys.map((y, i) => {
        const hot = fr.target === i;
        return (
          <line key={i} x1={lb.x + 50} y1={lb.y} x2={600} y2={y} stroke={hot ? C.gold : C.muted}
            strokeOpacity={hot ? 1 : 0.35} strokeWidth={hot ? 4 : 2.5} strokeLinecap="round" />
        );
      })}
      {fr.target !== undefined && (
        <circle cx={lb.x + 50 + (600 - lb.x - 50) * progress} cy={lb.y + (ys[fr.target] - lb.y) * progress} r="8" fill={C.gold} />
      )}
      <g transform={`translate(${lb.x} ${lb.y})`}>
        <circle r="48" fill={C.panel} stroke={C.teal} strokeWidth="3" />
        <g transform="scale(1.05)"><LB c={C.teal} /></g>
      </g>
      {fr.req > 0 && (
        <text x={lb.x} y={lb.y + 78} textAnchor="middle" fill={C.gold} fontSize="17" fontWeight="700">
          REQUEST {fr.req}{spec.algorithm === "ip-hash" && fr.client ? ` · ${fr.client}` : ""}
        </text>
      )}
      {ys.map((y, i) => {
        const hot = fr.target === i;
        const col = hot ? C.gold : C.teal;
        return (
          <g key={i}>
            <rect x="600" y={y - h / 2} width="350" height={h} rx="12" fill={C.panel} stroke={col} strokeWidth={hot ? 4 : 2.5} />
            <text x="620" y={y + 6} fill={col} fontSize="17" fontWeight="700" letterSpacing="1">SERVER {i + 1}</text>
            {Array.from({ length: Math.min(6, fr.loads[i]) }, (_, k) => (
              <circle key={k} cx={745 + k * 22} cy={y} r="8" fill={C.gold} fillOpacity=".85" />
            ))}
            <text x="936" y={y + 6} textAnchor="end" fill={C.muted} fontSize="15">served {fr.served[i]}</text>
          </g>
        );
      })}
      <text x="775" y={ys[0] - h / 2 - 8} textAnchor="middle" fill={C.muted} fontSize="13" letterSpacing="2">ACTIVE CONNECTIONS</text>
      <Note text={fr.note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const balancerVisual = {
  type: "balancer" as const, schema: balancerSchema, Component: BalancerDiagram, plannerHint: HINTS.balancer,
};

/* ───────────── consistent hashing ring ───────────── */

export const ringSchema = z.object({
  type: z.literal("ring"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  nodes: z.array(z.string().min(1).max(8)).min(2).max(5),
  keys: z.array(z.string().min(1).max(8)).min(3).max(10),
  addNode: z.string().max(8).optional(),
  vnodes: z.number().int().min(1).max(3).optional(),
});
export type RingSpec = z.infer<typeof ringSchema>;

export const RingDiagram: React.FC<{ spec: RingSpec; duration: number }> = ({ spec, duration }) => {
  const { s } = useT();
  const frames = useMemo(() => ringTrace(spec.nodes, spec.keys, spec.addNode, spec.vnodes ?? 1), [spec]);
  const { frame: fr } = useTrace(frames, duration);
  const cx = 500, cy = 195, R = 128;
  const at = (deg: number, r: number) => {
    const a = (deg / 360) * Math.PI * 2 - Math.PI / 2;
    return { x: cx + Math.cos(a) * r, y: cy + Math.sin(a) * r };
  };
  const names = spec.addNode ? [...spec.nodes, spec.addNode] : spec.nodes;
  const color = (name: string) => ACCENTS[Math.max(0, names.indexOf(name)) % ACCENTS.length];

  return (
    <>
      <circle cx={cx} cy={cy} r={R} fill="none" stroke={C.muted} strokeOpacity=".45" strokeWidth="3" />
      {fr.active && (() => {
        const k = fr.keys.find((x) => x.name === fr.active);
        const sorted = [...fr.points].sort((a, b) => a.pos - b.pos);
        const owner = k ? sorted.find((p) => p.pos >= k.pos) ?? sorted[0] : undefined;
        if (!k || !owner) return null;
        const a = at(k.pos, R), b = at(owner.pos, R);
        return <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={C.gold} strokeWidth="3" strokeDasharray="7 6" strokeLinecap="round" />;
      })()}
      {fr.keys.map((k, ki) => {
        const p = at(k.pos, R), lab = at(k.pos, R - (ki % 2 ? 44 : 26));
        const moved = fr.moved.includes(k.name);
        const active = fr.active === k.name;
        return (
          <g key={k.name}>
            <circle cx={p.x} cy={p.y} r={active || moved ? 9 : 7} fill={color(k.owner)}
              stroke={moved ? C.red : active ? C.gold : "none"} strokeWidth="3" />
            <text x={lab.x} y={lab.y + 4} textAnchor="middle" fill={moved ? C.red : C.white} fontSize="12">{k.name}</text>
          </g>
        );
      })}
      {fr.points.map((p, i) => {
        const pt = at(p.pos, R), lab = at(p.pos, R + 36);
        const isNew = fr.added === p.name;
        const first = fr.points.findIndex((q) => q.name === p.name) === i;
        return (
          <g key={`${p.name}${i}`}>
            <circle cx={pt.x} cy={pt.y} r="15" fill={C.panel} stroke={color(p.name)} strokeWidth={isNew ? 5 : 3.5} />
            <rect x={pt.x - 7} y={pt.y - 6} width="14" height="12" rx="2" fill={color(p.name)} fillOpacity=".7" />
            {first && (
              <text x={lab.x} y={lab.y + 5} textAnchor="middle" fill={color(p.name)} fontSize="17" fontWeight="700">{p.name}</text>
            )}
          </g>
        );
      })}
      <text x={cx} y={cy - 4} textAnchor="middle" fill={C.muted} fontSize="14" letterSpacing="2">HASH RING</text>
      <text x={cx} y={cy + 16} textAnchor="middle" fill={C.muted} fontSize="13">clockwise ↻</text>
      <Note text={fr.note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const ringVisual = {
  type: "ring" as const, schema: ringSchema, Component: RingDiagram, plannerHint: HINTS.ring,
};

/* ───────────── cache ───────────── */

export const cacheSchema = z.object({
  type: z.literal("cache"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  capacity: z.number().int().min(2).max(5),
  policy: z.enum(["lru", "fifo", "lfu"]).catch("lru"),
  accesses: z.array(z.string().min(1).max(6)).min(4).max(14),
});
export type CacheSpec = z.infer<typeof cacheSchema>;

export const CacheDiagram: React.FC<{ spec: CacheSpec; duration: number }> = ({ spec, duration }) => {
  const { s } = useT();
  const frames = useMemo(() => cacheTrace(spec.capacity, spec.policy, spec.accesses), [spec]);
  const { frame: fr } = useTrace(frames, duration);
  const n = spec.capacity;
  const w = Math.min(130, 860 / n - 14);
  const x0 = (1000 - n * (w + 14)) / 2 + 7;
  const y = 150, h = 84;
  const total = fr.hits + fr.misses;
  const rate = total ? Math.round((fr.hits / total) * 100) : 0;
  const ends =
    spec.policy === "lru" ? ["LEAST RECENT", "MOST RECENT"] : spec.policy === "fifo" ? ["OLDEST", "NEWEST"] : ["", ""];

  return (
    <>
      <text x="40" y="44" fill={C.muted} fontSize="15" fontWeight="700" letterSpacing="3">{spec.policy.toUpperCase()} CACHE</text>
      {fr.key && (
        <g>
          <text x="500" y="60" textAnchor="middle" fill={C.muted} fontSize="15" letterSpacing="3">READ</text>
          <rect x="450" y="70" width="100" height="44" rx="10" fill={fr.hit ? C.teal : C.red} fillOpacity=".25"
            stroke={fr.hit ? C.teal : C.red} strokeWidth="3" />
          <text x="500" y="100" textAnchor="middle" fill={C.white} fontSize="24" fontWeight="700">{fr.key}</text>
          <text x="570" y="100" fill={fr.hit ? C.teal : C.red} fontSize="22" fontWeight="800" letterSpacing="2">
            {fr.hit ? "HIT" : "MISS"}
          </text>
        </g>
      )}
      {Array.from({ length: n }, (_, i) => {
        const key = fr.slots[i];
        const x = x0 + i * (w + 14);
        const victim = fr.victim === i && fr.slots.length >= n;
        const justRead = key !== undefined && key === fr.key;
        const col = victim ? C.red : justRead ? C.gold : C.teal;
        return (
          <g key={i}>
            {key === undefined ? (
              <rect x={x} y={y} width={w} height={h} rx="12" fill="none" stroke={C.muted} strokeOpacity=".5"
                strokeWidth="2.5" strokeDasharray="8 7" />
            ) : (
              <>
                <rect x={x} y={y} width={w} height={h} rx="12" fill={col} fillOpacity=".18" stroke={col} strokeWidth="3.5" />
                <text x={x + w / 2} y={y + h / 2 + 9} textAnchor="middle" fill={C.white} fontSize="30" fontWeight="700">{key}</text>
                {spec.policy === "lfu" && (
                  <text x={x + w - 10} y={y + 22} textAnchor="end" fill={C.muted} fontSize="14">×{fr.freqs[i]}</text>
                )}
              </>
            )}
            {victim && (
              <text x={x + w / 2} y={y + h + 26} textAnchor="middle" fill={C.red} fontSize="14" fontWeight="700" letterSpacing="2">NEXT OUT</text>
            )}
          </g>
        );
      })}
      {ends[0] && (
        <>
          <text x={x0} y={y - 12} fill={C.muted} fontSize="13" letterSpacing="2">{ends[0]}</text>
          <text x={x0 + n * (w + 14) - 14} y={y - 12} textAnchor="end" fill={C.muted} fontSize="13" letterSpacing="2">{ends[1]}</text>
        </>
      )}
      {fr.evicted && (
        <text x="500" y="290" textAnchor="middle" fill={C.red} fontSize="20" fontWeight="700">EVICTED: {fr.evicted}</text>
      )}
      <g fontSize="18" fontWeight="700" textAnchor="middle">
        <text x="330" y="335" fill={C.teal}>HITS {fr.hits}</text>
        <text x="500" y="335" fill={C.red}>MISSES {fr.misses}</text>
        <text x="670" y="335" fill={C.gold}>HIT RATE {rate}%</text>
      </g>
      <Note text={fr.note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const cacheVisual = {
  type: "cache" as const, schema: cacheSchema, Component: CacheDiagram, plannerHint: HINTS.cache,
};
