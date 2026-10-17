import React, { useMemo } from "react";
import { z } from "zod";
import { C, Footnote, Note, useT, useTrace } from "./kit";
import { buildBst, layoutTree, treeTrace } from "./algorithms";
import { HINTS } from "./hints";

export const treeSchema = z.object({
  type: z.literal("tree"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  values: z.array(z.number()).min(1).max(9),
  algorithm: z.enum(["none", "insert", "inorder", "preorder", "postorder", "bfs"]).catch("none"),
});
export type TreeSpec = z.infer<typeof treeSchema>;

const R = 26;

export const TreeDiagram: React.FC<{ spec: TreeSpec; duration: number }> = ({ spec, duration }) => {
  const { s } = useT();
  const tree = useMemo(() => buildBst(spec.values), [spec.values]);
  const layout = useMemo(() => layoutTree(tree), [tree]);
  const frames = useMemo(() => treeTrace(tree, spec.algorithm), [tree, spec.algorithm]);
  const { frame: fr, progress } = useTrace(frames, duration);

  const step = Math.min(100, 840 / Math.max(1, layout.count - 1));
  const levelH = Math.min(78, 250 / Math.max(1, layout.maxDepth));
  const at = (v: number) => {
    const p = layout.pos.get(v)!;
    return { x: 500 + (p.idx - (layout.count - 1) / 2) * step, y: 60 + p.depth * levelH };
  };

  const shown = new Set(fr.shown);
  const visited = new Set(fr.visited ?? []);
  const path = new Set(fr.path ?? []);

  const edges: [number, number][] = [];
  tree.nodes.forEach((n, v) => {
    if (n.l !== undefined) edges.push([v, n.l]);
    if (n.r !== undefined) edges.push([v, n.r]);
  });

  return (
    <>
      {edges.filter(([a, b]) => shown.has(a) && shown.has(b)).map(([a, b]) => {
        const pa = at(a), pb = at(b);
        const dx = pb.x - pa.x, dy = pb.y - pa.y, len = Math.hypot(dx, dy) || 1;
        const hot = path.has(a) && (path.has(b) || fr.active === b);
        return (
          <line key={`${a}-${b}`} x1={pa.x + (dx / len) * R} y1={pa.y + (dy / len) * R}
            x2={pb.x - (dx / len) * R} y2={pb.y - (dy / len) * R}
            stroke={hot ? C.teal : C.muted} strokeOpacity={hot ? 1 : 0.5} strokeWidth="3" strokeLinecap="round" />
        );
      })}
      {tree.order.filter((v) => shown.has(v)).map((v) => {
        const { x, y } = at(v);
        const active = fr.active === v;
        const col = active ? C.gold : visited.has(v) ? C.teal : path.has(v) ? C.teal : C.purple;
        const fill = active ? 0.35 : visited.has(v) ? 0.5 : 0.15;
        const scale = active ? 1 + 0.15 * Math.sin(progress * Math.PI) : 1;
        return (
          <g key={v} transform={`translate(${x} ${y}) scale(${scale})`}>
            <circle r={R} fill={C.panel} />
            <circle r={R} fill={col} fillOpacity={fill} stroke={col} strokeWidth="3" />
            <text y="7" textAnchor="middle" fill={C.white} fontSize="21" fontWeight="700">{v}</text>
          </g>
        );
      })}
      {fr.visited && fr.visited.length > 0 && (
        <text x="500" y="362" textAnchor="middle" fill={C.teal} fontSize="19" fontWeight="600" letterSpacing="1">
          ORDER: {fr.visited.join(" → ")}
        </text>
      )}
      <Note text={fr.note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const treeVisual = {
  type: "tree" as const,
  schema: treeSchema,
  Component: TreeDiagram,
  plannerHint: HINTS.tree,
};