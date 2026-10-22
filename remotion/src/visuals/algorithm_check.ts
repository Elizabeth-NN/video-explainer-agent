/** Run: npx tsx src/visuals/algorithm_check.ts   (exits non-zero on failure) */
import assert from "node:assert/strict";
import { arrayTrace } from "./array";
import {
  binarySearch, bubbleSort, buildBst, buildMergeSortStory, chainTrace,
  graphTrace, insertionSort, linearSearch, mergeSort,
  mergeSortPhaseFromNarration, selectionSort, traversalOrder, treeTrace,
} from "./algorithms";

const input = [5, 2, 9, 1, 7, 3];
const sorted = [...input].sort((a, b) => a - b);
const last = <T,>(xs: T[]) => xs[xs.length - 1];

for (const [name, fn] of [["bubble", bubbleSort], ["selection", selectionSort], ["insertion", insertionSort]] as const) {
  const frames = fn(input);
  assert.deepEqual(last(frames).values, sorted, `${name} sort result`);
  assert.equal(last(frames).done?.length, input.length, `${name} marks all done`);
  // every frame must be a permutation of the input
  for (const f of frames) {
    assert.deepEqual([...f.values].sort((a, b) => a - b), sorted, `${name} permutation`);
    for (const index of f.compare ?? []) {
      assert.ok(index >= 0 && index < input.length, `${name} compare index`);
    }
    for (const index of f.swap ?? []) {
      assert.ok(index >= 0 && index < input.length, `${name} swap index`);
    }
  }
}

assert.equal(last(binarySearch(input, 7)).found, sorted.indexOf(7), "binary search finds 7");
assert.equal(last(binarySearch(input, 4)).found, undefined, "binary search misses 4");
assert.equal(last(linearSearch(input, 9)).found, 2, "linear search finds 9");

assert.deepEqual(last(mergeSort(input)).values, sorted, "merge sort result");
// -0 and 0 are equal under <= but distinct under Object.is, so a stable merge
// keeps the original -0 first; an unstable one would emit [0, -0].
assert.deepEqual(last(mergeSort([-0, 0])).values, [-0, 0], "merge sort is stable on equal values");

const mergeFrames = mergeSort(input);
assert.equal(mergeFrames.length, 12, "legacy merge sort keeps its frame count");
assert.equal(mergeFrames[0].stage, "start", "merge sort starts with a start frame");
assert.equal(last(mergeFrames).stage, "sorted", "merge sort ends with a sorted frame");

const mergeStageCounts = mergeFrames.reduce<Record<string, number>>(
  (counts, frame) => {
    if (frame.stage) counts[frame.stage] = (counts[frame.stage] ?? 0) + 1;
    return counts;
  },
  {},
);
assert.deepEqual(
  mergeStageCounts,
  { start: 1, split: 5, merge: 5, sorted: 1 },
  "legacy merge sort stage counts",
);

/* ── dedicated Merge Sort story ── */
const story = buildMergeSortStory(input);
assert.deepEqual(story.sorted, sorted, "merge story result");
assert.equal(story.splits.length, input.length - 1, "split count");
assert.equal(story.merges.length, input.length - 1, "merge count");
assert.deepEqual(story.tree.values, input, "story tree starts with input");

for (const split of story.splits) {
  assert.ok(split.lo <= split.mid && split.mid < split.hi, "split bounds");
  assert.deepEqual(
    [...split.left, ...split.right],
    input.slice(split.lo, split.hi + 1),
    "split children preserve the original run",
  );
}

for (const pass of story.merges) {
  assert.deepEqual(pass.left, [...pass.left].sort((a, b) => a - b), "left run sorted");
  assert.deepEqual(pass.right, [...pass.right].sort((a, b) => a - b), "right run sorted");
  assert.deepEqual(
    [...pass.left, ...pass.right].sort((a, b) => a - b),
    pass.output.slice(pass.lo, pass.hi + 1),
    "merge output is the union of its runs",
  );
  for (const step of pass.steps) {
    if (step.kind === "compare") {
      assert.ok(step.i >= 0 && step.i < pass.left.length, "compare i bounds");
      assert.ok(step.j >= 0 && step.j < pass.right.length, "compare j bounds");
      assert.equal(
        step.take,
        step.leftValue <= step.rightValue ? "left" : "right",
        "compare uses the stable tie-break",
      );
    } else if (step.kind === "take-left" || step.kind === "take-right") {
      assert.equal(step.output[step.k], step.value, "take writes its value");
    } else {
      assert.equal(step.output[step.k], step.value, "append writes its value");
    }
  }
}

assert.ok(
  story.merges.some((pass) =>
    pass.steps.some(
      (step) => step.kind === "append-left" || step.kind === "append-right",
    ),
  ),
  "merge story includes a remainder append",
);
const remainderStory = buildMergeSortStory([1, 2, 3, 7, 8, 9]);
assert.ok(
  remainderStory.merges.some((pass) =>
    pass.steps.some((step) => step.kind === "append-right"),
  ),
  "stable sorted halves append the remaining right run",
);
assert.deepEqual(
  buildMergeSortStory([-0, 0]).sorted,
  [-0, 0],
  "merge story is stable on equal values",
);

assert.equal(
  mergeSortPhaseFromNarration("Merge sort splits the list into halves."),
  "split",
  "phase split",
);
assert.equal(
  mergeSortPhaseFromNarration("It merges the sorted halves back together."),
  "merge",
  "phase merge",
);
assert.equal(
  mergeSortPhaseFromNarration("The final array is fully sorted."),
  "sorted",
  "phase sorted",
);
assert.equal(
  mergeSortPhaseFromNarration("Merge sort was invented by John von Neumann in 1945."),
  "overview",
  "phase overview",
);
assert.equal(
  mergeSortPhaseFromNarration(
    "Merge-insertion sort or the Ford-Johnson algorithm is a comparison sorting algorithm.",
  ),
  "overview",
  "Merge-Insertion is not Merge Sort",
);

const morePhaseCases = [
  ["The two halves are merged.", "merge"],
  ["The two halves are combined.", "merge"],
  ["The two sorted halves are merged.", "merge"],
  ["It merges adjacent pairs.", "merge"],
  ["It combines the results into one list.", "merge"],
  ["The result is a sorted array.", "sorted"],
  ["The result is an ordered list.", "sorted"],
  ["After sorting, the list is in ascending order.", "sorted"],
  ["It merges the sorted halves, and the final array is fully sorted.", "sorted"],
] as const;
for (const [narration, expected] of morePhaseCases) {
  assert.equal(
    mergeSortPhaseFromNarration(narration),
    expected,
    `phase for: ${narration}`,
  );
}

const mergePhaseStages = {
  overview: "start",
  split: "split",
  merge: "merge",
  sorted: "sorted",
} as const;
for (const phase of Object.keys(mergePhaseStages) as (keyof typeof mergePhaseStages)[]) {
  const stage = mergePhaseStages[phase];
  const frames = arrayTrace({
    type: "array",
    values: input,
    algorithm: "merge-sort",
    phase,
  });
  assert.ok(frames.length > 0, `merge sort ${phase} phase returns frames`);
  assert.ok(
    frames.every((frame) => frame.stage === stage),
    `merge sort ${phase} phase returns only ${stage} frames`,
  );
}
const invalidMergePhase = arrayTrace({
  type: "array",
  values: input,
  algorithm: "merge-sort",
  phase: "midpoint",
});
assert.equal(invalidMergePhase.length, 1, "invalid merge phase falls back to overview");
assert.equal(invalidMergePhase[0].stage, "start", "invalid merge phase uses start frame");

/* ── binary search phase behavior remains intact ── */
const binarySpec = (phase: "overview" | "midpoint" | "elimination" | "found" | "not-found") => ({
  type: "array" as const,
  values: input,
  algorithm: "binary-search" as const,
  target: 7,
  phase,
});
assert.equal(arrayTrace(binarySpec("overview")).length, 1, "binary overview");
assert.equal(arrayTrace(binarySpec("midpoint")).length, 1, "binary midpoint");
assert.ok(arrayTrace(binarySpec("elimination")).length > 0, "binary elimination");
assert.equal(arrayTrace(binarySpec("found")).length, 1, "binary found");
assert.ok(arrayTrace(binarySpec("not-found")).length > 0, "binary not-found");
assert.ok(
  arrayTrace(binarySpec("overview"))[0].values.every(
    (value, index, values) => index === 0 || values[index - 1] <= value,
  ),
  "binary overview is sorted",
);

const t = buildBst([8, 3, 10, 1, 6, 14, 4]);
assert.deepEqual(traversalOrder(t, "inorder"), [1, 3, 4, 6, 8, 10, 14], "inorder is sorted");
assert.deepEqual(traversalOrder(t, "preorder"), [8, 3, 1, 6, 4, 10, 14], "preorder");
assert.deepEqual(traversalOrder(t, "postorder"), [1, 4, 6, 3, 14, 10, 8], "postorder");
assert.deepEqual(traversalOrder(t, "bfs"), [8, 3, 10, 1, 6, 14, 4], "bfs");
assert.deepEqual(last(treeTrace(t, "insert")).shown, t.order, "insert trace ends with every node");

const st = chainTrace("stack", [1, 2, 3], [{ op: "pop" }, { op: "push", value: 9 }]);
assert.deepEqual(last(st).items, [1, 2, 9], "stack ops");
const q = chainTrace("queue", [1, 2, 3], [{ op: "dequeue" }]);
assert.deepEqual(last(q).items, [2, 3], "queue ops");
assert.equal(last(q).removed, 1, "queue reports removed item");

const ids = ["A", "B", "C", "D", "E"];
const edges = [
  { from: "A", to: "B" }, { from: "A", to: "C" }, { from: "B", to: "D" }, { from: "C", to: "E" },
];
assert.deepEqual(last(graphTrace(ids, edges, false, "A", "bfs")).visited, ["A", "B", "C", "D", "E"], "bfs order");
assert.deepEqual(last(graphTrace(ids, edges, false, "A", "dfs")).visited, ["A", "B", "D", "C", "E"], "dfs order");

console.log("all algorithm checks passed");