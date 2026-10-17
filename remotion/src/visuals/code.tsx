import React from "react";
import { z } from "zod";
import { C, Footnote, clip, stage, useT, useTrace, wrap } from "./kit";
import { HINTS } from "./hints";

export const codeSchema = z.object({
  type: z.literal("code"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  language: z.string().optional(),
  lines: z.array(z.string().max(44)).min(2).max(10),
  steps: z
    .array(
      z.object({
        line: z.number().int().min(1),
        note: z.string().optional(),
        output: z.string().optional(),
      }),
    )
    .max(8)
    .optional(),
});
export type CodeSpec = z.infer<typeof codeSchema>;

const MONO = "Menlo, Consolas, 'DejaVu Sans Mono', monospace";
const LH = 30;

export const CodeDiagram: React.FC<{ spec: CodeSpec; duration: number }> = ({ spec, duration }) => {
  const { frame, s } = useT();
  const n = spec.lines.length;
  const steps =
    spec.steps && spec.steps.length
      ? spec.steps.map((st) => ({ ...st, line: Math.min(n, Math.max(1, st.line)) }))
      : spec.lines.map((_, i) => ({ line: i + 1, note: undefined, output: undefined }));
  const { frame: cur, index } = useTrace(steps, duration);

  const outputs = steps
    .slice(0, index + 1)
    .map((st) => st.output)
    .filter((o): o is string => !!o)
    .slice(-4);
  const panelH = n * LH + 28;
  const p = stage(frame, 0, s(0.4));

  return (
    <>
      <g opacity={p}>
        <rect x="30" y="20" width="620" height={panelH} rx="14" fill="#0F1A2E" stroke="#33445C" strokeWidth="2" />
        {spec.language && (
          <text x="636" y="42" textAnchor="end" fill={C.muted} fontSize="13" letterSpacing="2">
            {spec.language.toUpperCase()}
          </text>
        )}
      </g>
      {spec.lines.map((ln, i) => {
        const o = stage(frame, s(0.1) + i * s(0.07), s(0.3));
        const active = cur.line === i + 1;
        const y = 34 + i * LH;
        return (
          <g key={i} opacity={o}>
            {active && (
              <>
                <rect x="36" y={y + 2} width="608" height={LH - 2} rx="6" fill={C.gold} fillOpacity=".16" />
                <rect x="36" y={y + 2} width="4" height={LH - 2} rx="2" fill={C.gold} />
              </>
            )}
            <text x="66" y={y + 22} textAnchor="end" fill={C.muted} fontSize="14" fontFamily={MONO}>{i + 1}</text>
            <text x="82" y={y + 22} fill={active ? C.white : C.muted} fontSize="19" fontFamily={MONO}
              xmlSpace="preserve" style={{ whiteSpace: "pre" }}>{ln}</text>
          </g>
        );
      })}

      <g opacity={p}>
        <text x="680" y="48" fill={C.teal} fontSize="14" fontWeight="700" letterSpacing="3">WHAT HAPPENS</text>
        {cur.note &&
          wrap(cur.note, 26, 5).map((ln, i) => (
            <text key={i} x="680" y={82 + i * 26} fill={C.white} fontSize="19">{ln}</text>
          ))}
        <text x="680" y="250" fill={C.gold} fontSize="14" fontWeight="700" letterSpacing="3">OUTPUT</text>
        {outputs.map((o, i) => (
          <text key={i} x="680" y={282 + i * 26} fill={C.gold} fontSize="19" fontFamily={MONO}>
            {clip(o, 26)}
          </text>
        ))}
      </g>
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const codeVisual = {
  type: "code" as const,
  schema: codeSchema,
  Component: CodeDiagram,
  plannerHint: HINTS.code,
};
