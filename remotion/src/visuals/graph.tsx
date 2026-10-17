import React, { useMemo } from "react";
import { z } from "zod";
import { C, Footnote, Note, arrowPath, clip, useT, useTrace } from "./kit";
import { graphTrace, type GraphFrame } from "./algorithms";
import { HINTS } from "./hints";

export const graphSchema = z.object({
  type: z.literal("graph"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  nodes: z.array(z.string().min(1)).min(2).max(8),
  edges: z.array(z.object({ from: z.string(), to: z.string() })).min(1).max(14),
  directed: z.boolean().optional(),
  algorithm: z.enum(["none", "bfs", "dfs"]).catch("none"),
  start: z.string().optional(),
});
export type GraphSpec = z.infer<typeof graphSchema>;

const R = 30;

export const GraphDiagram: React.FC<{ spec: GraphSpec; duration: number }> = ({ spec, duration }) => {
  const { s } = useT();
  const ids = useMemo(() => [...new Set(spec.nodes)], [spec.nodes]);
  const directed = !!spec.directed;

  const frames: GraphFrame[] = useMemo(
    () =>
      spec.algorithm === "none"
        ? [{ visited: [], pending: [], note: "" }]
        : graphTrace(ids, spec.edges, directed, spec.start ?? ids[0], spec.algorithm),
    [ids, spec.edges, directed, spec.start, spec.algorithm],
  );
  const { frame: fr } = useTrace(frames, duration);

  const n = ids.length;
  const pos = new Map(
    ids.map((id, i) => {
      const a = -Math.PI / 2 + (i / n) * Math.PI * 2;
      return [id, { x: 500 + 300 * Math.cos(a), y: 190 + 130 * Math.sin(a) }] as const;
    }),
  );

  const isHot = (a: string, b: string) =>
    !!fr.edge && ((fr.edge[0] === a && fr.edge[1] === b) || (!directed && fr.edge[0] === b && fr.edge[1] === a));

  const pendingLabel = spec.algorithm === "dfs" ? "STACK" : "QUEUE";
  const pending = spec.algorithm === "dfs" ? [...fr.pending].reverse() : fr.pending;

  return (
    <>
      {spec.edges.map((e, i) => {
        const a = pos.get(e.from), b = pos.get(e.to);
        if (!a || !b || e.from === e.to) return null;
        const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
        const ux = dx / len, uy = dy / len;
        const hot = isHot(e.from, e.to);
        const col = hot ? C.gold : C.muted;
        const x2 = b.x - ux * (R + (directed ? 8 : 0)), y2 = b.y - uy * (R + (directed ? 8 : 0));
        return (
          <g key={i} opacity={hot ? 1 : 0.6}>
            <line x1={a.x + ux * R} y1={a.y + uy * R} x2={x2} y2={y2} stroke={col}
              strokeWidth={hot ? 4 : 3} strokeLinecap="round" />
            {directed && (
              <path d={arrowPath(x2, y2, ux, uy)} fill="none" stroke={col} strokeWidth="3"
                strokeLinecap="round" strokeLinejoin="round" />
            )}
          </g>
        );
      })}
      {ids.map((id) => {
        const p = pos.get(id)!;
        const order = fr.visited.indexOf(id);
        const active = fr.active === id;
        const col = active ? C.gold : order >= 0 ? C.teal : C.purple;
        const fill = active ? 0.4 : order >= 0 ? 0.45 : 0.15;
        return (
          <g key={id} transform={`translate(${p.x} ${p.y})`}>
            <circle r={R} fill={C.panel} />
            <circle r={R} fill={col} fillOpacity={fill} stroke={col} strokeWidth="3" />
            <text y="7" textAnchor="middle" fill={C.white} fontSize={id.length > 3 ? 15 : 21}
              fontWeight="700">{clip(id, 8)}</text>
            {order >= 0 && (
              <g transform={`translate(${R - 4} ${-R + 4})`}>
                <circle r="11" fill={C.bg} stroke={col} strokeWidth="2" />
                <text y="5" textAnchor="middle" fill={col} fontSize="13" fontWeight="700">{order + 1}</text>
              </g>
            )}
          </g>
        );
      })}
      {spec.algorithm !== "none" && (
        <text x="30" y="30" fill={C.muted} fontSize="17" fontWeight="600" letterSpacing="1">
          {pendingLabel}: {pending.length ? pending.join("  ") : "empty"}
        </text>
      )}
      <Note text={fr.note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const graphVisual = {
  type: "graph" as const,
  schema: graphSchema,
  Component: GraphDiagram,
  plannerHint: HINTS.graph,
};
