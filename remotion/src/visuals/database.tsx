import React, { useMemo } from "react";
import { z } from "zod";
import { ACCENTS, C, Footnote, Note, arrowPath, clip, stage, useT, useTrace } from "./kit";
import { binarySearch, linearSearch, type ArrayFrame } from "./algorithms";
import {
  type Cell, type Query, joinColumns, joinTrace, rangeLabels, replicationTrace, shardTrace, sqlOf, tableTrace,
} from "./systems";
import { HINTS } from "./hints";

const MONO = "Menlo, Consolas, 'DejaVu Sans Mono', monospace";
const zCell = z.union([z.string().max(18), z.number()]);

/* ───────────── shared table renderer ───────────── */

type Tone = "gold" | "red" | "teal";
const DataTable: React.FC<{
  x: number; y: number; cols: string[]; rows: Cell[][]; colW: number; rowH: number; font?: number;
  hiRows?: number[]; hiTone?: Tone; dimOthers?: boolean; dimCols?: string[];
  changed?: [number, number][]; added?: number; hiRows2?: number[];
}> = ({ x, y, cols, rows, colW, rowH, font = 17, hiRows = [], hiTone = "gold", dimOthers, dimCols = [], changed = [], added, hiRows2 = [] }) => {
  const tone = { gold: C.gold, red: C.red, teal: C.teal }[hiTone];
  const width = cols.length * colW;
  const isDim = (c: string) => dimCols.some((d) => d.toLowerCase() === c.toLowerCase());
  return (
    <g>
      <rect x={x} y={y} width={width} height={rowH + 2} rx="8" fill={C.teal} fillOpacity=".18" stroke={C.teal} strokeWidth="2" />
      {cols.map((c, j) => (
        <text key={j} x={x + j * colW + colW / 2} y={y + rowH / 2 + font * 0.38 + 1} textAnchor="middle"
          fill={C.teal} fontSize={font - 2} fontWeight="700" letterSpacing="1" opacity={isDim(c) ? 0.25 : 1}>
          {clip(c.toUpperCase(), Math.floor(colW / 9))}
        </text>
      ))}
      {rows.map((r, i) => {
        const hot = hiRows.includes(i);
        const hot2 = hiRows2.includes(i);
        const isNew = added === i;
        const ry = y + (i + 1) * rowH + 4;
        const dimRow = dimOthers && !hot;
        const col = isNew ? C.teal : hot ? tone : hot2 ? C.purple : C.muted;
        return (
          <g key={i} opacity={dimRow ? 0.25 : 1}>
            <rect x={x} y={ry} width={width} height={rowH - 2} rx="6" fill={col}
              fillOpacity={hot || hot2 || isNew ? 0.2 : 0.06} stroke={col} strokeOpacity={hot || hot2 || isNew ? 1 : 0.35}
              strokeWidth={hot || hot2 || isNew ? 2.5 : 1.5} />
            {cols.map((c, j) => {
              const ch = changed.some(([a, b]) => a === i && b === j);
              return (
                <text key={j} x={x + j * colW + colW / 2} y={ry + rowH / 2 + font * 0.32} textAnchor="middle"
                  fill={ch ? C.gold : C.white} fontSize={font} fontWeight={ch ? 800 : 500}
                  opacity={isDim(c) ? 0.25 : 1}>
                  {clip(String(r[j] ?? ""), Math.floor(colW / 8.5))}
                </text>
              );
            })}
          </g>
        );
      })}
    </g>
  );
};

/* ───────────── table + SQL ───────────── */

const zWhere = z.object({
  column: z.string(),
  op: z.enum(["=", "!=", ">", "<", ">=", "<="]),
  value: zCell,
});

export const tableSchema = z.object({
  type: z.literal("table"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  name: z.string().max(16).optional(),
  columns: z.array(z.string().min(1).max(12)).min(2).max(5),
  rows: z.array(z.array(zCell)).min(1).max(7),
  query: z
    .object({
      kind: z.enum(["select", "update", "delete", "insert"]),
      where: zWhere.optional(),
      columns: z.array(z.string()).optional(),
      set: z.object({ column: z.string(), value: zCell }).optional(),
      values: z.array(zCell).optional(),
    })
    .optional(),
});
export type TableSpec = z.infer<typeof tableSchema>;

export const TableDiagram: React.FC<{ spec: TableSpec; duration: number }> = ({ spec, duration }) => {
  const { s } = useT();
  const name = spec.name ?? "users";
  const frames = useMemo(() => tableTrace(spec.columns, spec.rows, spec.query as Query | undefined), [spec]);
  const { frame: fr } = useTrace(frames, duration);
  const colW = Math.min(150, 880 / spec.columns.length);
  const x = (1000 - colW * spec.columns.length) / 2;
  const sql = spec.query ? sqlOf(name, spec.query as Query) : `${name}`;

  return (
    <>
      <text x="500" y="38" textAnchor="middle" fill={C.gold} fontSize="20" fontWeight="700" fontFamily={MONO}>
        {clip(sql, 70)}
      </text>
      <DataTable x={x} y={58} cols={spec.columns} rows={fr.rows} colW={colW} rowH={38}
        hiRows={fr.matched} hiTone={fr.danger ? "red" : "gold"} dimOthers={fr.dimOthers} dimCols={fr.dimCols}
        changed={fr.changed} added={fr.added} />
      <Note text={fr.note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const tableVisual = {
  type: "table" as const, schema: tableSchema, Component: TableDiagram, plannerHint: HINTS.table,
};

/* ───────────── join ───────────── */

const zSide = z.object({
  name: z.string().min(1).max(12),
  columns: z.array(z.string().min(1).max(10)).min(2).max(3),
  rows: z.array(z.array(zCell)).min(1).max(4),
});

export const joinSchema = z.object({
  type: z.literal("join"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  left: zSide,
  right: zSide,
  on: z.object({ left: z.string(), right: z.string() }),
  joinType: z.enum(["inner", "left"]).catch("inner"),
});
export type JoinSpec = z.infer<typeof joinSchema>;

export const JoinDiagram: React.FC<{ spec: JoinSpec; duration: number }> = ({ spec, duration }) => {
  const { s } = useT();
  const { left, right } = spec;
  const frames = useMemo(
    () => joinTrace({ cols: left.columns, rows: left.rows }, { cols: right.columns, rows: right.rows }, spec.on.left, spec.on.right, spec.joinType),
    [spec, left, right],
  );
  const { frame: fr } = useTrace(frames, duration);
  const resultCols = joinColumns(left.name, left.columns, right.name, right.columns);
  const rW = Math.min(130, 900 / resultCols.length);
  const sql = `SELECT * FROM ${left.name} ${spec.joinType === "left" ? "LEFT" : "INNER"} JOIN ${right.name} ON ${left.name}.${spec.on.left} = ${right.name}.${spec.on.right}`;
  const shown = fr.result.slice(0, 5);

  return (
    <>
      <text x="500" y="20" textAnchor="middle" fill={C.gold} fontSize="14" fontWeight="700" fontFamily={MONO}>{clip(sql, 96)}</text>
      <text x="60" y="44" fill={C.teal} fontSize="14" fontWeight="700" letterSpacing="3">{left.name.toUpperCase()}</text>
      <text x="940" y="44" textAnchor="end" fill={C.purple} fontSize="14" fontWeight="700" letterSpacing="3">{right.name.toUpperCase()}</text>
      <DataTable x={60} y={50} cols={left.columns} rows={left.rows.map((r) => left.columns.map((_, i) => r[i] ?? "NULL"))}
        colW={96} rowH={26} font={15} hiRows={fr.leftHi === undefined ? [] : [fr.leftHi]} />
      <DataTable x={652} y={50} cols={right.columns} rows={right.rows.map((r) => right.columns.map((_, i) => r[i] ?? "NULL"))}
        colW={96} rowH={26} font={15} hiRows2={fr.rightHi} />
      <text x="500" y="108" textAnchor="middle" fill={C.muted} fontSize="30">⋈</text>
      <text x="500" y="134" textAnchor="middle" fill={C.muted} fontSize="13">
        {clip(`${spec.on.left} = ${spec.on.right}`, 22)}
      </text>
      <text x="500" y="200" textAnchor="middle" fill={C.gold} fontSize="14" fontWeight="700" letterSpacing="3">RESULT</text>
      <DataTable x={(1000 - resultCols.length * rW) / 2} y={208} cols={resultCols} rows={shown} colW={rW} rowH={26} font={15}
        hiRows={shown.length ? [shown.length - 1] : []} hiTone="teal" />
      {fr.result.length > 5 && (
        <text x="940" y="200" textAnchor="end" fill={C.muted} fontSize="13">+ {fr.result.length - 5} more rows</text>
      )}
      <Note text={fr.note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const joinVisual = {
  type: "join" as const, schema: joinSchema, Component: JoinDiagram, plannerHint: HINTS.join,
};

/* ───────────── index vs full scan ───────────── */

export const indexscanSchema = z.object({
  type: z.literal("indexscan"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  values: z.array(z.number().min(0)).min(6).max(12),
  target: z.number(),
});
export type IndexScanSpec = z.infer<typeof indexscanSchema>;

const checked = (frames: ArrayFrame[], upTo: number) =>
  frames.slice(0, Math.min(frames.length, upTo + 1)).filter((f) => f.pointer !== undefined).length;

export const IndexScanDiagram: React.FC<{ spec: IndexScanSpec; duration: number }> = ({ spec, duration }) => {
  const { s } = useT();
  const values = useMemo(() => [...new Set(spec.values)], [spec.values]);
  const scan = useMemo(() => linearSearch(values, spec.target), [values, spec.target]);
  const idx = useMemo(() => binarySearch(values, spec.target), [values, spec.target]);
  const steps = Math.max(scan.length, idx.length);
  const ticks = useMemo(() => Array.from({ length: steps }, (_, i) => i), [steps]);
  const { index } = useTrace(ticks, duration);
  const a = scan[Math.min(index, scan.length - 1)];
  const b = idx[Math.min(index, idx.length - 1)];
  const n = values.length;
  const slot = Math.min(72, 880 / n);
  const x0 = (1000 - n * slot) / 2;
  const final = index >= steps - 1;

  const lane = (fr: ArrayFrame, y: number, title: string, count: number, col: string) => (
    <g>
      <text x="60" y={y - 18} fill={col} fontSize="15" fontWeight="700" letterSpacing="3">{title}</text>
      <text x="940" y={y - 18} textAnchor="end" fill={col} fontSize="17" fontWeight="700">ROWS CHECKED: {count}</text>
      {fr.values.map((v, i) => {
        const found = fr.found === i;
        const cur = fr.pointer === i;
        const out = fr.range && (i < fr.range[0] || i > fr.range[1]);
        const c = found ? C.teal : cur ? C.gold : C.purple;
        return (
          <g key={i} opacity={out ? 0.3 : 1}>
            <rect x={x0 + i * slot + 4} y={y} width={slot - 8} height="52" rx="8" fill={c} fillOpacity={found ? 0.5 : cur ? 0.35 : 0.14}
              stroke={c} strokeWidth="3" />
            <text x={x0 + i * slot + slot / 2} y={y + 33} textAnchor="middle" fill={C.white} fontSize="19" fontWeight="700">{v}</text>
          </g>
        );
      })}
    </g>
  );

  return (
    <>
      <text x="500" y="30" textAnchor="middle" fill={C.gold} fontSize="18" fontWeight="700" fontFamily={MONO}>
        WHERE id = {spec.target}
      </text>
      {lane(a, 90, "FULL TABLE SCAN", checked(scan, index), C.red)}
      {lane(b, 220, "INDEX LOOKUP (SORTED)", checked(idx, index), C.teal)}
      <Note text={final ? `Scan checked ${checked(scan, steps)} rows, the index only ${checked(idx, steps)}` : index === 0 ? "Same query, two ways to find the row" : (a.note ?? "")} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const indexscanVisual = {
  type: "indexscan" as const, schema: indexscanSchema, Component: IndexScanDiagram, plannerHint: HINTS.indexscan,
};

/* ───────────── replication ───────────── */

export const replicationSchema = z.object({
  type: z.literal("replication"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  replicas: z.number().int().min(1).max(3),
  mode: z.enum(["sync", "async"]).catch("async"),
  writes: z.number().int().min(2).max(4),
  failover: z.boolean().optional(),
});
export type ReplicationSpec = z.infer<typeof replicationSchema>;

export const ReplicationDiagram: React.FC<{ spec: ReplicationSpec; duration: number }> = ({ spec, duration }) => {
  const { s } = useT();
  const frames = useMemo(
    () => replicationTrace(spec.replicas, spec.mode, spec.writes, !!spec.failover),
    [spec],
  );
  const { frame: fr, progress } = useTrace(frames, duration);
  const n = spec.replicas + 1;
  const ys = (i: number) => (i === 0 ? 195 : 195 + (i - 1 - (spec.replicas - 1) / 2) * 105);
  const xs = (i: number) => (i === 0 ? 70 : 600);
  const W = 330;

  return (
    <>
      <text x="500" y="34" textAnchor="middle" fill={C.gold} fontSize="17" fontWeight="700" letterSpacing="2">
        {spec.mode.toUpperCase()} REPLICATION · ACKNOWLEDGED WRITES: {fr.acked}
      </text>
      {Array.from({ length: spec.replicas }, (_, k) => {
        const i = k + 1;
        const hot = fr.arrow?.[1] === i;
        return (
          <line key={i} x1={xs(0) + 270} y1={ys(0)} x2={xs(i) - 6} y2={ys(i)} stroke={hot ? C.gold : C.muted}
            strokeOpacity={hot ? 1 : 0.35} strokeWidth={hot ? 4 : 2.5} strokeDasharray={hot ? undefined : "7 7"} strokeLinecap="round" />
        );
      })}
      {fr.arrow && (
        <circle cx={xs(0) + 270 + (xs(fr.arrow[1]) - 6 - xs(0) - 270) * progress}
          cy={ys(0) + (ys(fr.arrow[1]) - ys(0)) * progress} r="8" fill={C.gold} />
      )}
      {Array.from({ length: n }, (_, i) => {
        const role = fr.role[i];
        const col = role === "down" ? C.red : role === "primary" ? C.gold : C.teal;
        const label = role === "down" ? "DOWN" : role === "primary" ? (i === 0 ? "PRIMARY" : "NEW PRIMARY") : `REPLICA ${i}`;
        const x = xs(i), y = ys(i);
        const bw = i === 0 ? 270 : W;
        return (
          <g key={i} opacity={role === "down" ? 0.7 : 1}>
            <rect x={x} y={y - 42} width={bw} height="84" rx="14" fill={C.panel} stroke={col} strokeWidth="3.5"
              strokeDasharray={role === "down" ? "9 7" : undefined} />
            <text x={x + 18} y={y - 14} fill={col} fontSize="16" fontWeight="800" letterSpacing="2">{label}</text>
            {Array.from({ length: spec.writes }, (_, k) => {
              const has = fr.applied[i] > k;
              return (
                <g key={k}>
                  <rect x={x + 18 + k * 48} y={y + 2} width="38" height="28" rx="6" fill={has ? col : "none"}
                    fillOpacity=".55" stroke={col} strokeWidth="2" strokeOpacity={has ? 1 : 0.4} strokeDasharray={has ? undefined : "5 4"} />
                  <text x={x + 37 + k * 48} y={y + 22} textAnchor="middle" fill={C.white} fontSize="14" fontWeight="700" opacity={has ? 1 : 0.4}>
                    W{k + 1}
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

export const replicationVisual = {
  type: "replication" as const, schema: replicationSchema, Component: ReplicationDiagram, plannerHint: HINTS.replication,
};

/* ───────────── sharding ───────────── */

export const shardingSchema = z.object({
  type: z.literal("sharding"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  shards: z.number().int().min(2).max(4),
  keys: z.array(z.string().min(1).max(8)).min(4).max(10),
  strategy: z.enum(["hash", "range"]).catch("hash"),
});
export type ShardingSpec = z.infer<typeof shardingSchema>;

export const ShardingDiagram: React.FC<{ spec: ShardingSpec; duration: number }> = ({ spec, duration }) => {
  const { s } = useT();
  const frames = useMemo(() => shardTrace(spec.shards, spec.keys, spec.strategy), [spec]);
  const { frame: fr } = useTrace(frames, duration);
  const n = spec.shards;
  const w = Math.min(200, 900 / n - 24);
  const slot = w + 24;
  const x0 = (1000 - n * slot) / 2 + 12;
  const ranges = rangeLabels(n);
  const top = 108, bodyH = 232;

  return (
    <>
      <text x="40" y="34" fill={C.muted} fontSize="15" fontWeight="700" letterSpacing="3">
        {spec.strategy === "hash" ? `HASH(KEY) MOD ${n}` : "RANGE BY FIRST LETTER"}
      </text>
      {fr.active && (() => {
        const tx = x0 + fr.active.shard * slot + w / 2;
        return (
          <>
            <line x1="500" y1="84" x2={tx} y2={top - 4} stroke={C.gold} strokeWidth="3.5" strokeLinecap="round" />
            <path d={arrowPath(tx, top - 4, (tx - 500) / Math.hypot(tx - 500, top - 88), (top - 88) / Math.hypot(tx - 500, top - 88))}
              fill="none" stroke={C.gold} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
            <rect x="440" y="48" width="120" height="38" rx="10" fill={C.gold} fillOpacity=".25" stroke={C.gold} strokeWidth="3" />
            <text x="500" y="74" textAnchor="middle" fill={C.white} fontSize="19" fontWeight="700">{clip(fr.active.key, 9)}</text>
          </>
        );
      })()}
      {fr.shards.map((keys, i) => {
        const x = x0 + i * slot;
        const col = ACCENTS[i % ACCENTS.length];
        const hot = fr.active?.shard === i;
        return (
          <g key={i}>
            <rect x={x} y={top} width={w} height={bodyH} rx="14" fill={C.panel} stroke={col} strokeWidth={hot ? 4.5 : 3} />
            <text x={x + w / 2} y={top + 28} textAnchor="middle" fill={col} fontSize="17" fontWeight="800" letterSpacing="2">SHARD {i + 1}</text>
            {spec.strategy === "range" && (
              <text x={x + w / 2} y={top + 48} textAnchor="middle" fill={C.muted} fontSize="13" letterSpacing="2">{ranges[i]}</text>
            )}
            {keys.slice(0, 7).map((k, j) => (
              <g key={j}>
                <rect x={x + 14} y={top + 58 + j * 22} width={w - 28} height="19" rx="5" fill={col}
                  fillOpacity={fr.active?.key === k ? 0.5 : 0.18} />
                <text x={x + w / 2} y={top + 72 + j * 22} textAnchor="middle" fill={C.white} fontSize="13">{clip(k, 12)}</text>
              </g>
            ))}
            {keys.length > 7 && (
              <text x={x + w / 2} y={top + bodyH - 8} textAnchor="middle" fill={C.muted} fontSize="13">+{keys.length - 7} more</text>
            )}
            <text x={x + w / 2} y={top + bodyH + 20} textAnchor="middle" fill={col} fontSize="15" fontWeight="700">{keys.length} key{keys.length === 1 ? "" : "s"}</text>
          </g>
        );
      })}
      <Note text={fr.note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const shardingVisual = {
  type: "sharding" as const, schema: shardingSchema, Component: ShardingDiagram, plannerHint: HINTS.sharding,
};
