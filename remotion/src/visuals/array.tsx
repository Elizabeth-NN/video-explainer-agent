import React, { useMemo } from "react";
import { z } from "zod";
import { C, Footnote, Note, stage, useT, useTrace } from "./kit";
import {
  type ArrayFrame, type MergeSortNode, type MergeSortPass, type MergeSortStep,
  ARRAY_ALGORITHMS, binarySearch, bubbleSort, buildMergeSortStory,
  insertionSort, isBinarySearchPhase, isMergeSortPhase, linearSearch,
  mergeSort, selectionSort, walkArray,
} from "./algorithms";
import { HINTS } from "./hints";

export const arraySchema = z.object({
  type: z.literal("array"),
  title: z.string().optional(),
  footnote: z.string().optional(),
  values: z.array(z.number().min(0)).min(2).max(10),
  algorithm: z.enum(ARRAY_ALGORITHMS).default("none"),
  target: z.number().optional(),
  phase: z.enum([
    "overview",
    "midpoint",
    "elimination",
    "found",
    "not-found",
    "split",
    "merge",
    "sorted",
  ]).optional(),
});
export type ArraySpec = z.infer<typeof arraySchema>;

const MERGE_STAGE_BY_PHASE: Partial<
  Record<NonNullable<ArraySpec["phase"]>, ArrayFrame["stage"]>
> = {
  overview: "start",
  split: "split",
  merge: "merge",
  sorted: "sorted",
};

export const arrayTrace = (spec: ArraySpec): ArrayFrame[] => {
  const target = spec.target ?? spec.values[Math.floor(spec.values.length / 2)];

  if (spec.algorithm === "merge-sort" && spec.phase) {
    const frames = mergeSort(spec.values);
    // A binary-search phase on a Merge Sort spec used to return every frame.
    // Default to the overview instead of replaying the whole algorithm.
    if (!isMergeSortPhase(spec.phase)) {
      return frames.length ? [frames[0]] : frames;
    }
    const stage = MERGE_STAGE_BY_PHASE[spec.phase];
    const matching = stage
      ? frames.filter((frame) => frame.stage === stage)
      : [];
    return matching.length ? matching : frames;
  }

  if (spec.algorithm === "binary-search" && spec.phase) {
    const frames = binarySearch(spec.values, target);

    if (!isBinarySearchPhase(spec.phase)) {
      const values = [...spec.values].sort((a, b) => a - b);
      return [{
        values,
        range: [0, values.length - 1],
        note: `Sorted array; looking for ${target}`,
      }];
    }

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
    case "merge-sort": return mergeSort(spec.values);
    case "binary-search": return binarySearch(spec.values, target);
    case "linear-search": return linearSearch(spec.values, target);
    default: return walkArray(spec.values);
  }
};

const SORTS = ["bubble-sort", "selection-sort", "insertion-sort", "merge-sort"];

const look = (i: number, fr: ArrayFrame) => {
  if (fr.found === i) return { col: C.teal, fill: 0.55, op: 1 };
  if (fr.swap?.includes(i)) return { col: C.red, fill: 0.4, op: 1 };
  if (fr.compare?.includes(i) || fr.pointer === i) return { col: C.gold, fill: 0.35, op: 1 };
  if (fr.done?.includes(i)) return { col: C.teal, fill: 0.35, op: 1 };
  const outside = fr.range && (i < fr.range[0] || i > fr.range[1]);
  return { col: C.purple, fill: 0.15, op: outside ? 0.3 : 1 };
};

/* ───────────── merge sort rendering ───────────── */

type CompareStep = Extract<MergeSortStep, { kind: "compare" }>;
type TakeStep = Extract<MergeSortStep, { kind: "take-left" | "take-right" }>;
type AppendStep = Extract<MergeSortStep, { kind: "append-left" | "append-right" }>;

type MergeDisplay =
  | { kind: "start"; pass: MergeSortPass }
  | {
      kind: "take";
      pass: MergeSortPass;
      compare: CompareStep;
      take: TakeStep;
      side: "left" | "right";
      k: number;
      output: number[];
    }
  | {
      kind: "append";
      pass: MergeSortPass;
      side: "left" | "right";
      values: number[];
      startIndex: number;
      k: number;
      output: number[];
    }
  | { kind: "done"; pass: MergeSortPass };

/** Pick a merge pass that is large enough to teach, preferring one with a remainder. */
const pickMergePass = (
  merges: MergeSortPass[],
  durationFrames = Number.POSITIVE_INFINITY,
): MergeSortPass | undefined => {
  if (!merges.length) return undefined;
  const remainder = merges.filter((pass) =>
    pass.steps.some(
      (step) => step.kind === "append-left" || step.kind === "append-right",
    ),
  );
  const useful = remainder.filter(
    (pass) => pass.left.length + pass.right.length >= 3,
  );

  // A 4-second scene cannot read a full 7-value merge at a comfortable pace.
  // Prefer a compact 3-5 value pass when the scene is short.
  if (durationFrames < 150) {
    const compact = useful.filter(
      (pass) => pass.left.length + pass.right.length <= 5,
    );
    if (compact.length) {
      return compact.reduce((best, pass) =>
        pass.left.length + pass.right.length >
        best.left.length + best.right.length
          ? pass
          : best,
      );
    }
  }

  if (useful.length) {
    return useful.reduce((best, pass) =>
      pass.left.length + pass.right.length >
      best.left.length + best.right.length
        ? pass
        : best,
    );
  }
  return merges[merges.length - 1];
};

/**
 * Collapse compare/take pairs into one display event and group consecutive
 * remainder appends. This keeps the merge view followable on a 4-second scene
 * instead of flashing through every internal loop iteration.
 */
const buildMergeDisplays = (pass: MergeSortPass): MergeDisplay[] => {
  const displays: MergeDisplay[] = [{ kind: "start", pass }];
  let index = 0;

  while (index < pass.steps.length) {
    const step = pass.steps[index];

    if (step.kind === "compare") {
      const next = pass.steps[index + 1];
      if (next && (next.kind === "take-left" || next.kind === "take-right")) {
        const take = next;
        displays.push({
          kind: "take",
          pass,
          compare: step,
          take,
          side: take.kind === "take-left" ? "left" : "right",
          k: take.k,
          output: take.output,
        });
        index += 2;
        continue;
      }
      index += 1;
      continue;
    }

    if (step.kind === "append-left" || step.kind === "append-right") {
      const kind = step.kind;
      const side = kind === "append-left" ? "left" : "right";
      const values: number[] = [];
      const startIndex = step.index;
      let last: AppendStep = step;
      while (
        index < pass.steps.length &&
        pass.steps[index].kind === kind
      ) {
        const current = pass.steps[index] as AppendStep;
        values.push(current.value);
        last = current;
        index += 1;
      }
      displays.push({
        kind: "append",
        pass,
        side,
        values,
        startIndex,
        k: last.k,
        output: last.output,
      });
      continue;
    }

    index += 1;
  }

  displays.push({ kind: "done", pass });
  return displays;
};

const MergeLegend: React.FC = () => (
  <g transform="translate(45, 326)">
    {[
      { label: "compare", color: C.gold, fill: 0.1, dashed: false },
      { label: "left run", color: C.teal, fill: 0.28, dashed: false },
      { label: "right run", color: C.purple, fill: 0.28, dashed: false },
      { label: "written", color: C.teal, fill: 0.5, dashed: false },
      { label: "remainder", color: C.gold, fill: 0.3, dashed: true },
    ].map((item, index) => (
      <g key={item.label} transform={`translate(${index * 185}, 0)`}>
        <rect x="0" y="-9" width="16" height="12" rx="3"
          fill={item.color} fillOpacity={item.fill} stroke={item.color}
          strokeWidth="2" strokeDasharray={item.dashed ? "4 3" : undefined} />
        <text x="23" y="1" fill={C.muted} fontSize="12" fontWeight="600">
          {item.label}
        </text>
      </g>
    ))}
  </g>
);

const MergeSortDiagram: React.FC<{ spec: ArraySpec; duration: number }> = ({
  spec, duration,
}) => {
  const { frame, s } = useT();
  const story = useMemo(() => buildMergeSortStory(spec.values), [spec.values]);
  const phase = isMergeSortPhase(spec.phase) ? spec.phase : "overview";
  const n = story.input.length;

  const depthRows = useMemo(() => {
    const rows: MergeSortNode[][] = [];
    const walk = (node: MergeSortNode) => {
      (rows[node.depth] ??= []).push(node);
      node.children?.forEach(walk);
    };
    walk(story.tree);
    return rows;
  }, [story]);

  const mergePass = useMemo(
    () => pickMergePass(story.merges, duration),
    [story, duration],
  );
  const mergeDisplays = useMemo(
    () => (mergePass ? buildMergeDisplays(mergePass) : []),
    [mergePass],
  );

  const frames = useMemo<(number | MergeDisplay)[]>(() => {
    if (phase === "split") return depthRows.map((_, index) => index);
    if (phase === "merge") return mergeDisplays;
    return [0];
  }, [phase, depthRows, mergeDisplays]);

  const { frame: active, progress } = useTrace(frames, duration);
  const activeDepth = typeof active === "number" ? active : 0;
  const mergeDisplay =
    phase === "merge" && active && typeof active === "object"
      ? (active as MergeDisplay)
      : undefined;

  const arrayLayout = (count: number) => {
    const width = Math.min(76, 860 / Math.max(1, count));
    const gap = 8;
    const total = count * (width + gap) - gap;
    return { width, gap, x0: (1000 - total) / 2 };
  };

  if (phase === "overview") {
    const layout = arrayLayout(n);
    return (
      <>
        <text x="500" y="34" textAnchor="middle" fill={C.muted}
          fontSize="13" fontWeight="700" letterSpacing="3">
          MERGE SORT · DIVIDE → SORT → MERGE
        </text>
        <text x={layout.x0} y="78" fill={C.teal} fontSize="13"
          fontWeight="700" letterSpacing="2">ORIGINAL ARRAY</text>
        {story.input.map((value, index) => {
          const p = stage(frame, s(0.1) + index * s(0.05), s(0.4));
          const x = layout.x0 + index * (layout.width + layout.gap);
          return (
            <g key={`overview-${index}`} opacity={p}>
              <rect x={x} y="94" width={layout.width} height="52" rx="8"
                fill={C.purple} fillOpacity="0.22" stroke={C.purple} strokeWidth="3" />
              <text x={x + layout.width / 2} y="127" textAnchor="middle"
                fill={C.white} fontSize="21" fontWeight="700">{value}</text>
              <text x={x + layout.width / 2} y="162" textAnchor="middle"
                fill={C.muted} fontSize="12">{index}</text>
            </g>
          );
        })}
        {["1  DIVIDE", "2  SORT", "3  MERGE"].map((label, index) => {
          const p = stage(frame, s(0.25) + index * s(0.2), s(0.45));
          const cardWidth = 190;
          const x = 215 + index * 210;
          return (
            <g key={label} opacity={p}>
              <rect x={x} y="218" width={cardWidth} height="78" rx="12"
                fill={C.panel} stroke={index === 2 ? C.teal : C.gold}
                strokeOpacity="0.7" strokeWidth="2" />
              <text x={x + cardWidth / 2} y="264" textAnchor="middle"
                fill={index === 2 ? C.teal : C.gold} fontSize="18"
                fontWeight="700">{label}</text>
              {index < 2 && (
                <path d={`M${x + cardWidth + 4} 257 H${x + cardWidth + 18}`}
                  stroke={C.muted} strokeWidth="2" />
              )}
            </g>
          );
        })}
        <Note text="Divide the array, sort each run, then merge the runs." />
        <Footnote text={spec.footnote} at={s(1)} />
      </>
    );
  }

  if (phase === "split") {
    const activeSplits = story.splits.filter(
      (split) => split.depth === activeDepth,
    );
    const note = activeDepth === 0
      ? "Split the full array into two runs."
      : activeSplits.length
        ? `Split ${activeSplits.length} run${activeSplits.length === 1 ? "" : "s"} at depth ${activeDepth}.`
        : "Base case: each run holds one value.";

    return (
      <>
        <text x="500" y="24" textAnchor="middle" fill={C.muted}
          fontSize="13" fontWeight="700" letterSpacing="3">
          MERGE SORT · RECURSION TREE
        </text>
        {depthRows.map((nodes, depth) => nodes.map((node) => {
          const x = 42 + (node.lo / n) * 916;
          const width = Math.max(54, ((node.hi - node.lo + 1) / n) * 916 - 8);
          const y = 48 + depth * 64;
          const isActive = depth === activeDepth;
          const isPast = depth < activeDepth;
          const color = isActive ? C.gold : isPast ? C.teal : C.muted;
          const opacity = depth <= activeDepth ? 1 : 0.16;
          const fontSize = Math.max(
            12,
            Math.min(21, (width - 14) / Math.max(2, node.values.length)),
          );
          return (
            <g key={`node-${node.lo}-${node.hi}`} opacity={opacity}>
              {node.children?.map((child) => {
                const childX = 42 + (child.lo / n) * 916;
                const childWidth = Math.max(
                  54,
                  ((child.hi - child.lo + 1) / n) * 916 - 8,
                );
                return (
                  <line key={`edge-${child.lo}-${child.hi}`}
                    x1={x + width / 2} y1={y + 46}
                    x2={childX + childWidth / 2} y2={y + 64}
                    stroke={child.depth <= activeDepth ? C.teal : C.muted}
                    strokeOpacity={child.depth <= activeDepth ? 0.55 : 0.2}
                    strokeWidth="2" />
                );
              })}
              <rect x={x} y={y} width={width} height="46" rx="8"
                fill={color} fillOpacity={isActive ? 0.25 : 0.12}
                stroke={color} strokeWidth={isActive ? 3 : 2} />
              <text x={x + width / 2} y={y + 29} textAnchor="middle"
                fill={isActive ? C.gold : C.white} fontSize={fontSize}
                fontWeight="700">
                {node.values.join("  ")}
              </text>
            </g>
          );
        }))}
        {depthRows.map((_, depth) => (
          <text key={`depth-${depth}`} x="18" y={48 + depth * 64 + 28}
            fill={C.muted} fontSize="11" fontWeight="700">D{depth}</text>
        ))}
        <Note text={note} />
        <Footnote text={spec.footnote} at={s(1)} />
      </>
    );
  }

  if (phase === "sorted") {
    const layout = arrayLayout(n);
    return (
      <>
        <text x="500" y="34" textAnchor="middle" fill={C.muted}
          fontSize="13" fontWeight="700" letterSpacing="3">
          MERGE SORT · RESULT
        </text>
        <text x={layout.x0} y="78" fill={C.teal} fontSize="13"
          fontWeight="700" letterSpacing="2">SORTED ARRAY</text>
        {story.sorted.map((value, index) => {
          const p = stage(frame, s(0.1) + index * s(0.05), s(0.4));
          const x = layout.x0 + index * (layout.width + layout.gap);
          return (
            <g key={`sorted-${index}`} opacity={p}>
              <rect x={x} y="94" width={layout.width} height="52" rx="8"
                fill={C.teal} fillOpacity="0.3" stroke={C.teal} strokeWidth="3" />
              <text x={x + layout.width / 2} y="127" textAnchor="middle"
                fill={C.teal} fontSize="21" fontWeight="700">{value}</text>
              <text x={x + layout.width / 2} y="162" textAnchor="middle"
                fill={C.muted} fontSize="12">{index}</text>
            </g>
          );
        })}
        <g opacity={stage(frame, s(0.8), s(0.4))}>
          <circle cx="500" cy="250" r="28" fill={C.teal} fillOpacity="0.18"
            stroke={C.teal} strokeWidth="3" />
          <path d="M486 250 L496 260 L515 239" fill="none" stroke={C.teal}
            strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
          <text x="536" y="257" fill={C.teal} fontSize="17" fontWeight="700">
            Sorting complete
          </text>
        </g>
        <Note text="Sorted: smallest value first, largest value last." />
        <Footnote text={spec.footnote} at={s(1)} />
      </>
    );
  }

  if (!mergePass || !mergeDisplay) {
    return (
      <>
        <Note text="No merge steps are available for this array." />
        <Footnote text={spec.footnote} at={s(1)} />
      </>
    );
  }

  const compare = mergeDisplay.kind === "take"
    ? mergeDisplay.compare
    : mergeDisplay.kind === "start"
      ? mergeDisplays.find(
          (display): display is Extract<MergeDisplay, { kind: "take" }> =>
            display.kind === "take",
        )?.compare
      : undefined;
  const append = mergeDisplay.kind === "append" ? mergeDisplay : undefined;

  let leftPtr = 0;
  let rightPtr = 0;
  if (mergeDisplay.kind === "append") {
    leftPtr = mergeDisplay.pass.left.length;
    rightPtr = mergeDisplay.pass.right.length;
    if (mergeDisplay.side === "left") {
      leftPtr = mergeDisplay.startIndex;
    } else {
      rightPtr = mergeDisplay.startIndex;
    }
  } else if (mergeDisplay.kind === "done") {
    leftPtr = mergeDisplay.pass.left.length;
    rightPtr = mergeDisplay.pass.right.length;
  } else if (mergeDisplay.kind === "take") {
    const current = mergeDisplay.compare;
    leftPtr = mergeDisplay.side === "left" ? current.i + 1 : current.i;
    rightPtr = mergeDisplay.side === "right" ? current.j + 1 : current.j;
  } else if (compare) {
    leftPtr = compare.i;
    rightPtr = compare.j;
  }

  const outLength = mergeDisplay.pass.hi - mergeDisplay.pass.lo + 1;
  const writtenCount =
    mergeDisplay.kind === "start"
      ? 0
      : mergeDisplay.kind === "done"
        ? outLength
        : Math.max(
            0,
            Math.min(outLength, mergeDisplay.k - mergeDisplay.pass.lo + 1),
          );
  const output = mergeDisplay.kind === "start"
    ? []
    : mergeDisplay.kind === "done"
      ? mergeDisplay.pass.output.slice(
          mergeDisplay.pass.lo,
          mergeDisplay.pass.hi + 1,
        )
      : mergeDisplay.output.slice(
          mergeDisplay.pass.lo,
          mergeDisplay.pass.lo + writtenCount,
        );
  const outWidth = Math.min(76, 920 / Math.max(1, outLength) - 8);
  const outGap = 8;
  const outTotal = outLength * (outWidth + outGap) - outGap;
  const outX0 = (1000 - outTotal) / 2;
  const outY = 190;
  const outH = 50;

  const leftX = 45;
  const rightX = 525;
  const sourceWidth = 58;
  const sourceGap = 8;
  const sourceY = 60;
  const sourceH = 48;

  let nextK: number | undefined;
  if (mergeDisplay.kind === "take" || mergeDisplay.kind === "append") {
    nextK = mergeDisplay.k + 1;
  } else if (mergeDisplay.kind === "start") {
    nextK = mergeDisplay.pass.lo;
  }
  const kIndex = nextK === undefined ? -1 : nextK - mergeDisplay.pass.lo;

  const note = (() => {
    if (mergeDisplay.kind === "start") {
      return `Merge ${mergeDisplay.pass.left.length} left and ${mergeDisplay.pass.right.length} right values.`;
    }
    if (mergeDisplay.kind === "take") {
      return `Compared ${mergeDisplay.compare.leftValue} and ${mergeDisplay.compare.rightValue}: took ${mergeDisplay.take.value} from the ${mergeDisplay.side}.`;
    }
    if (mergeDisplay.kind === "append") {
      return `${mergeDisplay.side === "left" ? "Left" : "Right"} run exhausted: appended ${mergeDisplay.values.join(", ")}.`;
    }
    return `Merged into [${mergeDisplay.pass.output.slice(mergeDisplay.pass.lo, mergeDisplay.pass.hi + 1).join(", ")}].`;
  })();

  const renderRun = (
    values: number[],
    side: "left" | "right",
    startX: number,
    pointer: number,
  ) => {
    const color = side === "left" ? C.teal : C.purple;
    return (
      <>
        {values.map((value, index) => {
          const x = startX + index * (sourceWidth + sourceGap);
          const isCompareIndex = compare
            ? side === "left" ? compare.i === index : compare.j === index
            : false;
          const isChosen = compare
            ? compare.take === side &&
              (side === "left" ? compare.i : compare.j) === index
            : false;
          const isRemaining = append
            ? append.side === side && index >= append.startIndex
            : false;
          const consumed = index < pointer;
          const stroke = isCompareIndex || isRemaining ? C.gold : color;
          const fill = isChosen || isRemaining ? C.gold : color;
          return (
            <g key={`${side}-${index}`}
              opacity={consumed && !isChosen && !isRemaining ? 0.32 : 1}>
              <rect x={x} y={sourceY} width={sourceWidth} height={sourceH}
                rx="8" fill={fill} fillOpacity={isChosen || isRemaining ? 0.42 : 0.18}
                stroke={stroke} strokeWidth={isCompareIndex || isRemaining ? 3 : 2}
                strokeDasharray={isRemaining ? "5 3" : undefined} />
              <text x={x + sourceWidth / 2} y={sourceY + 31}
                textAnchor="middle" fill={isChosen || isRemaining ? C.gold : C.white}
                fontSize="20" fontWeight="700">{value}</text>
              <text x={x + sourceWidth / 2} y={sourceY + sourceH + 22}
                textAnchor="middle" fill={isCompareIndex ? C.gold : C.muted}
                fontSize="12">{index}</text>
            </g>
          );
        })}
        {!values.length && (
          <text x={startX} y={sourceY + 30} fill={C.muted} fontSize="13">
            empty
          </text>
        )}
      </>
    );
  };

  return (
    <>
      <text x="45" y="20" fill={C.muted} fontSize="13" fontWeight="700"
        letterSpacing="3">
        MERGE SORT · COMBINING RUNS
      </text>
      <text x="45" y="38" fill={C.teal} fontSize="12" fontWeight="700"
        letterSpacing="2">LEFT RUN</text>
      <text x={rightX} y="38" fill={C.purple} fontSize="12" fontWeight="700"
        letterSpacing="2">RIGHT RUN</text>
      <text x="500" y="160" textAnchor="middle" fill={C.muted} fontSize="12"
        fontWeight="700" letterSpacing="2">
        MERGING POSITIONS {mergeDisplay.pass.lo}–{mergeDisplay.pass.hi}
      </text>

      {renderRun(mergeDisplay.pass.left, "left", leftX, leftPtr)}
      {renderRun(mergeDisplay.pass.right, "right", rightX, rightPtr)}

      {leftPtr < mergeDisplay.pass.left.length && (
        <>
          <text x={leftX + leftPtr * (sourceWidth + sourceGap) + sourceWidth / 2}
            y="150" textAnchor="middle" fill={C.gold} fontSize="13"
            fontWeight="700">i</text>
          <path d={`M${leftX + leftPtr * (sourceWidth + sourceGap) + sourceWidth / 2} 136 v6`}
            stroke={C.gold} strokeWidth="2" />
        </>
      )}
      {rightPtr < mergeDisplay.pass.right.length && (
        <>
          <text x={rightX + rightPtr * (sourceWidth + sourceGap) + sourceWidth / 2}
            y="150" textAnchor="middle" fill={C.gold} fontSize="13"
            fontWeight="700">j</text>
          <path d={`M${rightX + rightPtr * (sourceWidth + sourceGap) + sourceWidth / 2} 136 v6`}
            stroke={C.gold} strokeWidth="2" />
        </>
      )}

      <text x={outX0} y="184" fill={C.teal} fontSize="12" fontWeight="700"
        letterSpacing="2">OUTPUT</text>
      {Array.from({ length: outLength }, (_, index) => {
        const value = output[index];
        const written = index < output.length;
        const isLast = written && index === output.length - 1 &&
          (mergeDisplay.kind === "take" || mergeDisplay.kind === "append");
        const x = outX0 + index * (outWidth + outGap);
        return (
          <g key={`out-${index}`}
            transform={`translate(0 ${isLast ? (1 - progress) * 6 : 0})`}
            opacity={isLast ? 0.75 + 0.25 * progress : 1}>
            <rect x={x} y={outY} width={outWidth} height={outH} rx="8"
              fill={written ? C.teal : C.panel}
              fillOpacity={written ? 0.34 : 0.4}
              stroke={written ? C.teal : C.muted}
              strokeOpacity={written ? 1 : 0.45}
              strokeWidth="3" strokeDasharray={written ? undefined : "5 4"} />
            {written && (
              <text x={x + outWidth / 2} y={outY + 32} textAnchor="middle"
                fill={C.teal} fontSize="20" fontWeight="700">{value}</text>
            )}
            <text x={x + outWidth / 2} y={outY + outH + 20}
              textAnchor="middle" fill={C.muted} fontSize="12">
              {mergeDisplay.pass.lo + index}
            </text>
          </g>
        );
      })}
      {kIndex >= 0 && kIndex < outLength && (
        <>
          <text x={outX0 + kIndex * (outWidth + outGap) + outWidth / 2}
            y={outY + outH + 38} textAnchor="middle" fill={C.gold}
            fontSize="13" fontWeight="700">k</text>
          <path d={`M${outX0 + kIndex * (outWidth + outGap) + outWidth / 2} ${outY + outH + 27} v8`}
            stroke={C.gold} strokeWidth="2" />
        </>
      )}
      <MergeLegend />
      <Note text={note} />
      <Footnote text={spec.footnote} at={s(1)} />
    </>
  );
};

const GenericArrayDiagram: React.FC<{ spec: ArraySpec; duration: number }> = ({ spec, duration }) => {
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

export const ArrayDiagram: React.FC<{ spec: ArraySpec; duration: number }> = ({
  spec, duration,
}) => spec.algorithm === "merge-sort"
  ? <MergeSortDiagram spec={spec} duration={duration} />
  : <GenericArrayDiagram spec={spec} duration={duration} />;

export const arrayVisual = {
  type: "array" as const,
  schema: arraySchema,
  Component: ArrayDiagram,
  plannerHint: HINTS.array,
};