/** Run: npx tsx src/visuals/algorithm_check.ts   (exits non-zero on failure) */
import assert from "node:assert/strict";
import {
  binarySearch, bubbleSort, buildBst, chainTrace, graphTrace, insertionSort,
  linearSearch, selectionSort, traversalOrder, treeTrace,
} from "./algorithms";

const input = [5, 2, 9, 1, 7, 3];
const sorted = [...input].sort((a, b) => a - b);
const last = <T,>(xs: T[]) => xs[xs.length - 1];

for (const [name, fn] of [["bubble", bubbleSort], ["selection", selectionSort], ["insertion", insertionSort]] as const) {
  const frames = fn(input);
  assert.deepEqual(last(frames).values, sorted, `${name} sort result`);
  assert.equal(last(frames).done?.length, input.length, `${name} marks all done`);
  // every frame must be a permutation of the input
  for (const f of frames) assert.deepEqual([...f.values].sort((a, b) => a - b), sorted, `${name} permutation`);
}

assert.equal(last(binarySearch(input, 7)).found, sorted.indexOf(7), "binary search finds 7");
assert.equal(last(binarySearch(input, 4)).found, undefined, "binary search misses 4");
assert.equal(last(linearSearch(input, 9)).found, 2, "linear search finds 9");

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