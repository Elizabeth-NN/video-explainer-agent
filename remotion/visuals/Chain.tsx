import React, { useMemo } from "react";
import { z } from "zod";
import { C, Footnote, Note, arrowPath, useT, useTrace } from "./kit";
import { chainTrace } from "./algorithms";
import { HINTS } from "./hints";

export const chainSchema = z.object({
  type: z.literal("chain"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  kind: z.enum(["stack", "queue", "linked-list"]).catch("linked-list"),
  values: z.array(z.number()).max(6).default([]),
  ops: z
    .array(
      z.object({
        op: z.enum(["push", "pop", "enqueue", "dequeue", "append", "prepend", "remove-first", "remove-last"]),
        value: z.number().optional(),
      }),
    )
    .max(8)
    .optional(),
});
export type ChainSpec = z.infer<typeof chainSchema>;

export const ChainDiagram: React.FC<{ spec: ChainSpec; duration: number }> = ({ spec, duration }) => {
  const { s } = useT();
  const frames = useMemo(
    () => chainTrace(spec.kind, spec.values, spec.ops),
    [spec.kind, spec.values, spec.ops],
  );
  const { frame: fr, progress } = useTrace(frames, duration);
  const maxLen = Math.max(1, ...frames.map((f) => f.items.length));
  const pop = 0.6 + 0.4 * Math.min(1, progress * 3);
  const n = fr.items.length;

  const removed = fr.removed !== undefined && (
    <text x="940" y="60" textAnchor="end" fill={C.red} fontSize="22" fontWeight="700">
      REMOVED: {fr.removed}
    </text>
  );

  if (spec.kind === "stack") {
    const h = Math.min(56, 300 / Math.max(4, maxLen));
    const x = 390, w = 220, bottom = 350;
    return (
      <>
        <path d={`M${x - 20} ${bottom + 4} H${x + w + 20}`} stroke={C.muted} strokeWidth="4" strokeLinecap="round" />
        {fr.items.map((v, i) => {
          const top = i === n - 1;
          const sc = top && fr.hi === i ? pop : 1;
          const cy = bottom - i * h - h / 2;
          return (
            <g key={i} transform={`translate(${x + w / 2} ${cy}) scale(${sc})`}>
              <rect x={-w / 2} y={-(h - 6) / 2} width={w} height={h - 6} rx="8"
                fill={top ? C.gold : C.teal} fillOpacity=".25" stroke={top ? C.gold : C.teal} strokeWidth="3" />
              <text y="7" textAnchor="middle" fill={C.white} fontSize="22" fontWeight="700">{v}</text>
            </g>
          );
        })}
        {n > 0 && (
          <text x={x + w + 40} y={bottom - (n - 1) * h - h / 2 + 6} fill={C.gold} fontSize="18"
            fontWeight="700" letterSpacing="2">← TOP</text>
        )}
        {removed}
        <Note text={fr.note} />
        <Footnote text={spec.footnote} at={s(1)} />
      </>
    );
  }

  const slot = Math.min(120, 860 / maxLen);
  const w = slot - 34;
  const x0 = (1000 - maxLen * slot) / 2 + 10;
  const y = 170, h = 66;
  const list = spec.kind === "linked-list";
  const first = list ? "HEAD" : "FRONT";
  const last = list ? "TAIL" : "BACK";

  return (
    <>
      {fr.items.map((v, i) => {
        const x = x0 + i * slot;
        const sc = fr.hi === i ? pop : 1;
        return (
          <g key={i}>
            <g transform={`translate(${x + w / 2} ${y + h / 2}) scale(${sc})`}>
              <rect x={-w / 2} y={-h / 2} width={w} height={h} rx="10"
                fill={C.teal} fillOpacity=".2" stroke={C.teal} strokeWidth="3" />
              <text y="8" textAnchor="middle" fill={C.white} fontSize="24" fontWeight="700">{v}</text>
            </g>
            {list && i < n - 1 && (
              <>
                <line x1={x + w + 4} y1={y + h / 2} x2={x + slot - 8} y2={y + h / 2}
                  stroke={C.muted} strokeWidth="3" strokeLinecap="round" />
                <path d={arrowPath(x + slot - 6, y + h / 2, 1, 0)} fill="none" stroke={C.muted}
                  strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
              </>
            )}
          </g>
        );
      })}
      {n > 0 && (
        <>
          <text x={x0 + w / 2} y={y + h + 34} textAnchor="middle" fill={C.gold} fontSize="17"
            fontWeight="700" letterSpacing="2">{n === 1 ? `${first} / ${last}` : first}</text>
          {n > 1 && (
            <text x={x0 + (n - 1) * slot + w / 2} y={y + h + 34} textAnchor="middle" fill={C.gold}
              fontSize="17" fontWeight="700" letterSpacing="2">{last}</text>
          )}
        </>
      )}
      {removed}
      <Note text={fr.note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const chainVisual = {
  type: "chain" as const,
  schema: chainSchema,
  Component: ChainDiagram,
  plannerHint: HINTS.chain,
};
