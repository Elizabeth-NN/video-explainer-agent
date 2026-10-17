import React, { useMemo } from "react";
import { z } from "zod";
import { C, Footnote, Note, arrowPath, clip, stage, useT, useTrace } from "./kit";
import { deployTrace, pipelineTrace, type PipeStatus } from "./systems";
import { HINTS } from "./hints";

/* ───────────── CI/CD pipeline ───────────── */

export const pipelineSchema = z.object({
  type: z.literal("pipeline"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  stages: z
    .array(
      z.object({
        name: z.string().min(1).max(12),
        jobs: z.array(z.string().max(14)).max(3).optional(),
        fail: z.boolean().optional(),
      }),
    )
    .min(3)
    .max(6),
});
export type PipelineSpec = z.infer<typeof pipelineSchema>;

const STATUS_COLOR: Record<PipeStatus, string> = {
  pending: C.muted, running: C.gold, pass: C.teal, fail: C.red, skipped: C.muted,
};

const StatusIcon: React.FC<{ status: PipeStatus; frame: number }> = ({ status, frame }) => {
  const c = STATUS_COLOR[status];
  return (
    <g>
      <circle r="16" fill={C.panel} stroke={c} strokeWidth="3" strokeOpacity={status === "pending" || status === "skipped" ? 0.5 : 1} />
      {status === "pass" && <path d="M-7 0 L-2 6 L8 -6" fill="none" stroke={c} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" />}
      {status === "fail" && <path d="M-6 -6 L6 6 M6 -6 L-6 6" fill="none" stroke={c} strokeWidth="4" strokeLinecap="round" />}
      {status === "skipped" && <path d="M-7 0 H7" stroke={c} strokeWidth="4" strokeLinecap="round" opacity=".6" />}
      {status === "running" && (
        <circle r="8" fill="none" stroke={c} strokeWidth="4" strokeLinecap="round" strokeDasharray="14 40"
          transform={`rotate(${frame * 14})`} />
      )}
    </g>
  );
};

export const PipelineDiagram: React.FC<{ spec: PipelineSpec; duration: number }> = ({ spec, duration }) => {
  const { frame, s } = useT();
  const frames = useMemo(() => pipelineTrace(spec.stages), [spec.stages]);
  const { frame: fr } = useTrace(frames, duration);
  const n = spec.stages.length;
  const slot = 920 / n;
  const w = Math.min(160, slot - 34);
  const x0 = (1000 - n * slot) / 2 + (slot - w) / 2;
  const top = 70;

  return (
    <>
      {spec.stages.map((st, i) => {
        const status = fr.status[i];
        const col = STATUS_COLOR[status];
        const x = x0 + i * slot;
        const jobs = st.jobs ?? [];
        const h = 94 + Math.max(1, jobs.length) * 38;
        const p = stage(frame, s(0.1) + i * s(0.12), s(0.4));
        const dim = status === "skipped" ? 0.45 : 1;
        return (
          <g key={i} opacity={p * dim}>
            <rect x={x} y={top} width={w} height={h} rx="14" fill={C.panel} stroke={col}
              strokeWidth={status === "running" ? 4 : 2.5} strokeDasharray={status === "skipped" ? "8 7" : undefined} />
            <g transform={`translate(${x + w / 2} ${top + 36})`}><StatusIcon status={status} frame={frame} /></g>
            <text x={x + w / 2} y={top + 78} textAnchor="middle" fill={col === C.muted ? C.white : col}
              fontSize="18" fontWeight="700" letterSpacing="1">{st.name.toUpperCase()}</text>
            {jobs.map((j, k) => (
              <g key={k}>
                <rect x={x + 12} y={top + 94 + k * 38} width={w - 24} height="30" rx="8" fill={col} fillOpacity=".14"
                  stroke={col} strokeOpacity=".7" strokeWidth="1.5" />
                <text x={x + w / 2} y={top + 114 + k * 38} textAnchor="middle" fill={C.white} fontSize="14">{clip(j, 14)}</text>
              </g>
            ))}
          </g>
        );
      })}
      {spec.stages.slice(0, -1).map((_, i) => {
        const x1 = x0 + i * slot + w + 4, x2 = x0 + (i + 1) * slot - 6;
        const col = STATUS_COLOR[fr.status[i]];
        return (
          <g key={`a${i}`} opacity={fr.status[i] === "pass" ? 1 : 0.4}>
            <line x1={x1} y1={top + 36} x2={x2} y2={top + 36} stroke={col} strokeWidth="3" strokeLinecap="round" />
            <path d={arrowPath(x2, top + 36, 1, 0)} fill="none" stroke={col} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        );
      })}
      <Note text={fr.note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const pipelineVisual = {
  type: "pipeline" as const, schema: pipelineSchema, Component: PipelineDiagram, plannerHint: HINTS.pipeline,
};

/* ───────────── deployment strategies ───────────── */

export const deploySchema = z.object({
  type: z.literal("deploy"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  strategy: z.enum(["rolling", "blue-green", "canary"]).catch("rolling"),
  instances: z.number().int().min(2).max(6),
  from: z.string().max(8).optional(),
  to: z.string().max(8).optional(),
});
export type DeploySpec = z.infer<typeof deploySchema>;

export const DeployDiagram: React.FC<{ spec: DeploySpec; duration: number }> = ({ spec, duration }) => {
  const { frame, s } = useT();
  const from = spec.from ?? "v1", to = spec.to ?? "v2";
  const frames = useMemo(() => deployTrace(spec.strategy, spec.instances, from, to), [spec, from, to]);
  const { frame: fr } = useTrace(frames, duration);

  const rows: (0 | 1)[] = spec.strategy === "blue-green" ? [0, 1] : [0];
  const bw = 520;
  const [t1, t2] = fr.traffic;
  const name = (v: 1 | 2) => (v === 1 ? from : to);
  const color = (v: 1 | 2) => (v === 1 ? C.teal : C.gold);

  return (
    <>
      <text x="500" y="38" textAnchor="middle" fill={C.muted} fontSize="14" fontWeight="700" letterSpacing="3">TRAFFIC</text>
      <defs>
        <mask id="traffic-track"><rect x={500 - bw / 2} y="50" width={bw} height="30" rx="15" fill="#fff" /></mask>
      </defs>
      <rect x={500 - bw / 2} y="50" width={bw} height="30" rx="15" fill={C.panel} />
      <g mask="url(#traffic-track)">
        {t1 > 0 && <rect x={500 - bw / 2} y="50" width={(bw * t1) / 100} height="30" fill={C.teal} fillOpacity=".8" />}
        {t2 > 0 && <rect x={500 - bw / 2 + (bw * t1) / 100} y="50" width={(bw * t2) / 100} height="30" fill={C.gold} fillOpacity=".85" />}
      </g>
      <rect x={500 - bw / 2} y="50" width={bw} height="30" rx="15" fill="none" stroke={C.muted} strokeOpacity=".4" strokeWidth="2" />
      <text x={500 - bw / 2} y="100" fill={C.teal} fontSize="17" fontWeight="700">{from.toUpperCase()} {t1}%</text>
      <text x={500 + bw / 2} y="100" textAnchor="end" fill={C.gold} fontSize="17" fontWeight="700">{to.toUpperCase()} {t2}%</text>

      {rows.map((row) => {
        const insts = fr.instances.filter((i) => i.row === row);
        const bwid = 92, gap = 16;
        const total = insts.length * (bwid + gap) - gap;
        const x0 = 500 - total / 2 + (spec.strategy === "blue-green" ? 30 : 0);
        const y = spec.strategy === "blue-green" ? 140 + row * 112 : 175;
        return (
          <g key={row}>
            {spec.strategy === "blue-green" && (
              <text x="60" y={y + 46} fill={row === 0 ? C.teal : C.gold} fontSize="16" fontWeight="700" letterSpacing="3">
                {row === 0 ? "BLUE" : "GREEN"}
              </text>
            )}
            {insts.map((inst, i) => {
              const col = color(inst.v);
              const x = x0 + i * (bwid + gap);
              const starting = inst.st === "starting";
              const idle = inst.st === "idle" || inst.st === "retired";
              const pulse = starting ? 0.5 + 0.5 * Math.sin(frame / 4) : 1;
              const pop = stage(frame, 0, s(0.3));
              return (
                <g key={i} opacity={(idle ? 0.55 : 1) * pop}>
                  <rect x={x} y={y} width={bwid} height="90" rx="12" fill={col} fillOpacity={starting ? 0.08 + 0.12 * pulse : 0.22}
                    stroke={col} strokeWidth="3.5" strokeDasharray={starting || idle ? "8 6" : undefined} />
                  <text x={x + bwid / 2} y={y + 44} textAnchor="middle" fill={C.white} fontSize="22" fontWeight="700">
                    {name(inst.v).toUpperCase()}
                  </text>
                  <text x={x + bwid / 2} y={y + 68} textAnchor="middle" fill={col} fontSize="11" fontWeight="700" letterSpacing="1">
                    {starting ? "STARTING" : idle ? "STANDBY" : "LIVE"}
                  </text>
                </g>
              );
            })}
          </g>
        );
      })}
      <Note text={fr.note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const deployVisual = {
  type: "deploy" as const, schema: deploySchema, Component: DeployDiagram, plannerHint: HINTS.deploy,
};
