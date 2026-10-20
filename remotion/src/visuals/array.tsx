import React, { useMemo } from "react";
import { z } from "zod";
import { C, Footnote, Note, stage, useT, useTrace } from "./kit";
import {
  type ArrayFrame, binarySearch, bubbleSort, insertionSort, linearSearch, selectionSort, walkArray,
} from "./algorithms";
import { HINTS } from "./hints";

export const arraySchema = z.object({
  type: z.literal("array"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  values: z.array(z.number().min(0)).min(2).max(10),
  algorithm: z
    .enum(["none", "bubble-sort", "selection-sort", "insertion-sort", "binary-search", "linear-search"])
    .catch("none"),
  target: z.number().optional(),
  phase: z.enum([
    "overview",
    "midpoint",
    "elimination",
    "found",
    "not-found",
  ]).optional(),
});
export type ArraySpec = z.infer<typeof arraySchema>;

const arrayTrace = (spec: ArraySpec): ArrayFrame[] => {
  const target = spec.target ?? spec.values[Math.floor(spec.values.length / 2)];

  if (spec.algorithm === "binary-search" && spec.phase) {
    const frames = binarySearch(spec.values, target);

    switch (spec.phase) {
      case "overview": {
        const values = [...spec.values].sort((a, b) => a - b);
        return [{
          values,
          range: [0, values.length - 1],
          note: `Sorted array; looking for ${target}`,
        }];
      }
      case "midpoint":
        return frames[1] ? [frames[1]] : frames;

            case "elimination": {
        const eliminationFrames = frames.filter(
          (frame) =>
            frame.pointer !== undefined ||
            (frame.range !== undefined &&
              frame.pointer === undefined &&
              frame.found === undefined),
        );

        return eliminationFrames.length > 0
          ? eliminationFrames
          : frames.slice(0, 1);
      }

      case "found": {
        const foundFrames = frames.filter(
          (frame) => frame.found !== undefined
        );
        return foundFrames.length ? foundFrames.slice(-1) : frames.slice(-1);
      }

      case "not-found":
        return frames;
    }
  }

  switch (spec.algorithm) {
    case "bubble-sort": return bubbleSort(spec.values);
    case "selection-sort": return selectionSort(spec.values);
    case "insertion-sort": return insertionSort(spec.values);
    case "binary-search": return binarySearch(spec.values, target);
    case "linear-search": return linearSearch(spec.values, target);
    default: return walkArray(spec.values);
  }
};

const SORTS = ["bubble-sort", "selection-sort", "insertion-sort"];

const look = (i: number, fr: ArrayFrame) => {
  if (fr.found === i) return { col: C.teal, fill: 0.55, op: 1 };
  if (fr.swap?.includes(i)) return { col: C.red, fill: 0.4, op: 1 };
  if (fr.compare?.includes(i) || fr.pointer === i) return { col: C.gold, fill: 0.35, op: 1 };
  if (fr.done?.includes(i)) return { col: C.teal, fill: 0.35, op: 1 };
  const outside = fr.range && (i < fr.range[0] || i > fr.range[1]);
  return { col: C.purple, fill: 0.15, op: outside ? 0.3 : 1 };
};

export const ArrayDiagram: React.FC<{ spec: ArraySpec; duration: number }> = ({ spec, duration }) => {
  const { frame, s } = useT();
  const frames = useMemo(() => arrayTrace(spec), [spec]);
  const { frame: fr } = useTrace(frames, duration);

  const n = fr.values.length;
  const slot = Math.min(90, 880 / n);
  const w = slot - 12;
  const x0 = (1000 - n * slot) / 2;
  const maxV = Math.max(...fr.values, 1);
  const bars = SORTS.includes(spec.algorithm);
  const base = 330;

  const tags: Record<number, string[]> = {};
  const tag = (i: number | undefined, label: string) => {
    if (i === undefined) return;
    (tags[i] ??= []).push(label);
  };
  if (spec.algorithm === "binary-search" && fr.range && fr.range[0] <= fr.range[1]) {
    tag(fr.range[0], "LOW");
    tag(fr.range[1], "HIGH");
    tag(fr.pointer, "MID");
  }

  return (
    <>
      {fr.values.map((v, i) => {
        const p = stage(frame, s(0.1) + i * s(0.08), s(0.4));
        const { col, fill, op } = look(i, fr);
        const x = x0 + i * slot + 6;
        const h = bars ? Math.max(10, (v / maxV) * 220) : 80;
        const y = bars ? base - h : 140;
        return (
          <g key={i} opacity={p * op}>
            <rect x={x} y={y} width={w} height={h} rx="8" fill={col} fillOpacity={fill}
              stroke={col} strokeWidth="3" />
            <text x={x + w / 2} y={bars ? y - 10 : y + h / 2 + 8} textAnchor="middle"
              fill={col === C.purple ? C.white : col} fontSize="22" fontWeight="700">{v}</text>
            <text x={x + w / 2} y={(bars ? base : y + h) + 26} textAnchor="middle"
              fill={C.muted} fontSize="14">{i}</text>
            {tags[i] && (
              <text x={x + w / 2} y={(bars ? base : y + h) + 50} textAnchor="middle"
                fill={C.gold} fontSize="14" fontWeight="700" letterSpacing="1">{tags[i].join(" · ")}</text>
            )}
          </g>
        );
      })}
      <Note text={fr.note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

export const arrayVisual = {
  type: "array" as const,
  schema: arraySchema,
  Component: ArrayDiagram,
  plannerHint: HINTS.array,
};