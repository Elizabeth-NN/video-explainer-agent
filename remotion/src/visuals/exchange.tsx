import React from "react";
import { z } from "zod";
import { C, Footnote, arrowPath, clip, stage, useT } from "./kit";
import { HINTS } from "./hints";

export const exchangeSchema = z.object({
  type: z.literal("exchange"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  actors: z.array(z.string().min(1)).min(2).max(4),
  messages: z
    .array(
      z.object({
        from: z.string(),
        to: z.string(),
        label: z.string(),
        reply: z.boolean().optional(),
      }),
    )
    .min(1)
    .max(7),
});
export type ExchangeSpec = z.infer<typeof exchangeSchema>;

export const ExchangeDiagram: React.FC<{ spec: ExchangeSpec; duration: number }> = ({ spec }) => {
  const { frame, s } = useT();
  const { actors } = spec;
  const n = actors.length;
  const xs = actors.map((_, i) => 150 + (i * 700) / (n - 1));
  const find = (name: string) =>
    actors.findIndex((a) => a.toLowerCase() === name.toLowerCase().trim());
  const msgs = spec.messages
    .map((m) => ({ ...m, a: find(m.from), b: find(m.to) }))
    .filter((m) => m.a >= 0 && m.b >= 0);

  const boxW = 150, boxH = 46, top = 16;
  const y0 = top + boxH + 40;
  const gap = Math.min(52, (372 - y0) / Math.max(1, msgs.length));
  const stepT = s(0.9);
  const first = s(0.9);

  return (
    <>
      {actors.map((name, i) => {
        const p = stage(frame, s(0.1) + i * s(0.2), s(0.4));
        return (
          <g key={i} opacity={p}>
            <rect x={xs[i] - boxW / 2} y={top} width={boxW} height={boxH} rx="10"
              fill={C.panel} stroke={C.teal} strokeWidth="2.5" />
            <text x={xs[i]} y={top + 30} textAnchor="middle" fill={C.teal} fontSize="17"
              fontWeight="700" letterSpacing="1">{clip(name.toUpperCase(), 15)}</text>
            <line x1={xs[i]} y1={top + boxH} x2={xs[i]} y2={385} stroke={C.muted}
              strokeOpacity=".4" strokeWidth="2" strokeDasharray="7 7" />
          </g>
        );
      })}
      {msgs.map((m, i) => {
        const start = first + i * stepT;
        const p = stage(frame, start, s(0.5));
        const lab = stage(frame, start, s(0.3));
        const y = y0 + i * gap;
        const col = m.reply ? C.gold : C.teal;
        const x1 = xs[m.a], x2 = xs[m.b];

        if (m.a === m.b) {
          const d = `M${x1} ${y} h46 v22 h-46`;
          return (
            <g key={i} opacity={p}>
              <path d={d} fill="none" stroke={col} strokeWidth="3" strokeLinecap="round"
                strokeLinejoin="round" pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - p} />
              <path d={arrowPath(x1, y + 22, -1, 0)} fill="none" stroke={col} strokeWidth="3"
                strokeLinecap="round" strokeLinejoin="round" opacity={stage(frame, start + s(0.35), s(0.2))} />
              <text x={x1 + 56} y={y + 16} fill={C.white} fontSize="15" opacity={lab}>{clip(m.label, 28)}</text>
            </g>
          );
        }

        const dir = Math.sign(x2 - x1);
        const tip = x1 + (x2 - x1) * p;
        const end = x2 - dir * 4;
        const head = stage(frame, start + s(0.35), s(0.2));
        return (
          <g key={i}>
            <line x1={x1} y1={y} x2={x1 + (end - x1) * p} y2={y} stroke={col} strokeWidth="3"
              strokeLinecap="round" strokeDasharray={m.reply ? "9 7" : undefined} />
            <path d={arrowPath(end, y, dir, 0)} fill="none" stroke={col} strokeWidth="3"
              strokeLinecap="round" strokeLinejoin="round" opacity={head} />
            {p > 0 && p < 1 && <circle cx={tip} cy={y} r="6" fill={col} />}
            <text x={(x1 + x2) / 2} y={y - 9} textAnchor="middle" fill={C.white} fontSize="15"
              stroke={C.bg} strokeWidth="5" paintOrder="stroke" opacity={lab}>{clip(m.label, 28)}</text>
          </g>
        );
      })}
      <Footnote text={spec.footnote} at={first + msgs.length * stepT + s(0.3)} />
    </>
  );
};

export const exchangeVisual = {
  type: "exchange" as const,
  schema: exchangeSchema,
  Component: ExchangeDiagram,
  plannerHint: HINTS.exchange,
};
