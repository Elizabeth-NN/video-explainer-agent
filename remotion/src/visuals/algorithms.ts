/**
 * Deterministic traces. The planner supplies INPUTS (values, edges, ops);
 * everything below computes the steps, so a video can't teach a wrong swap.
 * Pure functions, no React: test with `npx tsx visuals/algorithms.check.ts`.
 */

/* ───────────── arrays ───────────── */

export type ArrayAlgorithm =
  | "none" | "bubble-sort" | "selection-sort" | "insertion-sort" | "binary-search" | "linear-search";

export type ArrayFrame = {
  values: number[];
  compare?: [number, number];
  swap?: [number, number];
  found?: number;
  done?: number[];
  range?: [number, number];
  pointer?: number;
  note?: string;
};

export const bubbleSort = (input: number[]): ArrayFrame[] => {
  const a = [...input];
  const n = a.length;
  const frames: ArrayFrame[] = [{ values: [...a], note: "Unsorted" }];
  const done: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    for (let j = 0; j < n - 1 - i; j++) {
      frames.push({ values: [...a], compare: [j, j + 1], done: [...done], note: `Compare ${a[j]} and ${a[j + 1]}` });
      if (a[j] > a[j + 1]) {
        [a[j], a[j + 1]] = [a[j + 1], a[j]];
        frames.push({ values: [...a], swap: [j, j + 1], done: [...done], note: "Out of order, so swap" });
      }
    }
    done.push(n - 1 - i);
  }
  frames.push({ values: [...a], done: a.map((_, i) => i), note: "Sorted" });
  return frames;
};

export const selectionSort = (input: number[]): ArrayFrame[] => {
  const a = [...input];
  const n = a.length;
  const frames: ArrayFrame[] = [{ values: [...a], note: "Unsorted" }];
  const done: number[] = [];
  for (let i = 0; i < n - 1; i++) {
    let min = i;
    for (let j = i + 1; j < n; j++) {
      frames.push({ values: [...a], compare: [min, j], done: [...done], note: `Is ${a[j]} smaller than ${a[min]}?` });
      if (a[j] < a[min]) min = j;
    }
    if (min !== i) {
      [a[i], a[min]] = [a[min], a[i]];
      frames.push({ values: [...a], swap: [i, min], done: [...done], note: `Move the smallest to position ${i + 1}` });
    }
    done.push(i);
  }
  frames.push({ values: [...a], done: a.map((_, i) => i), note: "Sorted" });
  return frames;
};

export const insertionSort = (input: number[]): ArrayFrame[] => {
  const a = [...input];
  const n = a.length;
  const frames: ArrayFrame[] = [{ values: [...a], done: [0], note: "The first value is a sorted prefix" }];
  for (let i = 1; i < n; i++) {
    let j = i;
    while (j > 0) {
      const prefix = Array.from({ length: i + 1 }, (_, k) => k).filter((k) => k !== j && k !== j - 1);
      frames.push({ values: [...a], compare: [j - 1, j], done: prefix, note: `Compare ${a[j - 1]} and ${a[j]}` });
      if (a[j - 1] <= a[j]) break;
      [a[j - 1], a[j]] = [a[j], a[j - 1]];
      frames.push({ values: [...a], swap: [j - 1, j], done: prefix, note: "Shift it left" });
      j--;
    }
  }
  frames.push({ values: [...a], done: a.map((_, i) => i), note: "Sorted" });
  return frames;
};

/** Binary search needs sorted input, so the array is sorted first (and says so). */
export const binarySearch = (input: number[], target: number): ArrayFrame[] => {
  const a = [...input].sort((x, y) => x - y);
  const frames: ArrayFrame[] = [
    { values: a, range: [0, a.length - 1], note: `Sorted array, looking for ${target}` },
  ];
  let lo = 0;
  let hi = a.length - 1;
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2);
    frames.push({ values: a, range: [lo, hi], pointer: mid, note: `Check the middle: ${a[mid]}` });
    if (a[mid] === target) {
      frames.push({ values: a, range: [lo, hi], found: mid, note: `Found ${target} at index ${mid}` });
      return frames;
    }
    if (a[mid] < target) {
      lo = mid + 1;
      frames.push({ values: a, range: [lo, hi], note: `${a[mid]} < ${target}: keep the right half` });
    } else {
      hi = mid - 1;
      frames.push({ values: a, range: [lo, hi], note: `${a[mid]} > ${target}: keep the left half` });
    }
  }
  frames.push({ values: a, range: [lo, hi], note: `${target} is not in the array` });
  return frames;
};

export const linearSearch = (input: number[], target: number): ArrayFrame[] => {
  const a = [...input];
  const frames: ArrayFrame[] = [{ values: a, note: `Looking for ${target}` }];
  for (let i = 0; i < a.length; i++) {
    frames.push({ values: a, pointer: i, note: `Index ${i}: is ${a[i]} equal to ${target}?` });
    if (a[i] === target) {
      frames.push({ values: a, found: i, note: `Found ${target} at index ${i}` });
      return frames;
    }
  }
  frames.push({ values: a, note: `${target} is not in the array` });
  return frames;
};

export const walkArray = (input: number[]): ArrayFrame[] =>
  input.map((v, i) => ({ values: input, pointer: i, note: `Index ${i} holds ${v}` }));

/* ───────────── binary search trees ───────────── */

export type TreeAlgorithm = "none" | "insert" | "inorder" | "preorder" | "postorder" | "bfs";
export type BstNode = { v: number; l?: number; r?: number };
export type Bst = { root: number; nodes: Map<number, BstNode>; order: number[] };
export type TreeFrame = { shown: number[]; active?: number; path?: number[]; visited?: number[]; note?: string };

export const buildBst = (values: number[]): Bst => {
  const order = [...new Set(values)];
  const root = order[0];
  const nodes = new Map<number, BstNode>();
  for (const v of order) {
    nodes.set(v, { v });
    if (v === root) continue;
    let cur = root;
    for (;;) {
      const n = nodes.get(cur)!;
      if (v < cur) {
        if (n.l === undefined) { n.l = v; break; }
        cur = n.l;
      } else {
        if (n.r === undefined) { n.r = v; break; }
        cur = n.r;
      }
    }
  }
  return { root, nodes, order };
};

/** x = in-order index, y = depth. Computed from the FINAL tree so nodes never jump while inserting. */
export const layoutTree = (t: Bst) => {
  const pos = new Map<number, { depth: number; idx: number }>();
  let idx = 0;
  let maxDepth = 0;
  const go = (v: number | undefined, d: number) => {
    if (v === undefined) return;
    const n = t.nodes.get(v)!;
    go(n.l, d + 1);
    pos.set(v, { depth: d, idx: idx++ });
    maxDepth = Math.max(maxDepth, d);
    go(n.r, d + 1);
  };
  go(t.root, 0);
  return { pos, count: idx, maxDepth };
};

export const traversalOrder = (t: Bst, mode: "inorder" | "preorder" | "postorder" | "bfs"): number[] => {
  const out: number[] = [];
  if (mode === "bfs") {
    const q = [t.root];
    while (q.length) {
      const v = q.shift()!;
      out.push(v);
      const n = t.nodes.get(v)!;
      if (n.l !== undefined) q.push(n.l);
      if (n.r !== undefined) q.push(n.r);
    }
    return out;
  }
  const go = (v?: number) => {
    if (v === undefined) return;
    const n = t.nodes.get(v)!;
    if (mode === "preorder") out.push(v);
    go(n.l);
    if (mode === "inorder") out.push(v);
    go(n.r);
    if (mode === "postorder") out.push(v);
  };
  go(t.root);
  return out;
};

export const treeTrace = (t: Bst, algo: TreeAlgorithm): TreeFrame[] => {
  if (algo === "none") return [{ shown: t.order }];
  if (algo === "insert") {
    const frames: TreeFrame[] = [{ shown: [], note: "Empty tree" }];
    t.order.forEach((v, k) => {
      const prior = t.order.slice(0, k);
      if (k === 0) {
        frames.push({ shown: [v], active: v, note: `${v} becomes the root` });
        return;
      }
      // Every ancestor of v was inserted before v, so walking down the final tree is the real path.
      const path: number[] = [];
      let cur = t.root;
      while (cur !== v) {
        path.push(cur);
        const n = t.nodes.get(cur)!;
        frames.push({
          shown: prior, active: cur, path: [...path],
          note: `${v} ${v < cur ? "<" : ">"} ${cur}, so go ${v < cur ? "left" : "right"}`,
        });
        cur = (v < cur ? n.l : n.r)!;
      }
      frames.push({ shown: t.order.slice(0, k + 1), active: v, path, note: `Insert ${v}` });
    });
    return frames;
  }
  const order = traversalOrder(t, algo);
  const frames: TreeFrame[] = order.map((v, i) => ({
    shown: t.order, active: v, visited: order.slice(0, i + 1), note: `Visit ${v}`,
  }));
  frames.push({ shown: t.order, visited: order, note: "Traversal complete" });
  return frames;
};

/* ───────────── stacks, queues, linked lists ───────────── */

export type ChainKind = "linked-list" | "stack" | "queue";
export type ChainOp = "push" | "pop" | "enqueue" | "dequeue" | "append" | "prepend" | "remove-first" | "remove-last";
export type ChainFrame = { items: number[]; hi?: number; removed?: number; note: string };

export const chainTrace = (
  kind: ChainKind,
  values: number[],
  ops: { op: ChainOp; value?: number }[] = [],
): ChainFrame[] => {
  const items: number[] = [];
  const frames: ChainFrame[] = [
    { items: [], note: kind === "stack" ? "Empty stack" : kind === "queue" ? "Empty queue" : "Empty list" },
  ];
  const addOp: ChainOp = kind === "stack" ? "push" : kind === "queue" ? "enqueue" : "append";
  const all = [...values.map((value) => ({ op: addOp, value })), ...ops];

  for (const { op, value } of all) {
    switch (op) {
      case "push":
      case "enqueue":
      case "append": {
        const v = value ?? items.length + 1;
        items.push(v);
        const verb = op === "push" ? "Push" : op === "enqueue" ? "Enqueue" : "Append";
        frames.push({ items: [...items], hi: items.length - 1, note: `${verb} ${v}` });
        break;
      }
      case "prepend": {
        const v = value ?? items.length + 1;
        items.unshift(v);
        frames.push({ items: [...items], hi: 0, note: `Prepend ${v}` });
        break;
      }
      case "pop":
      case "remove-last": {
        if (!items.length) { frames.push({ items: [], note: "Nothing to remove" }); break; }
        const r = items.pop()!;
        frames.push({ items: [...items], removed: r, note: `${op === "pop" ? "Pop" : "Remove"} ${r}` });
        break;
      }
      case "dequeue":
      case "remove-first": {
        if (!items.length) { frames.push({ items: [], note: "Nothing to remove" }); break; }
        const r = items.shift()!;
        frames.push({ items: [...items], removed: r, note: `${op === "dequeue" ? "Dequeue" : "Remove"} ${r}` });
        break;
      }
    }
  }
  return frames;
};

/* ───────────── graphs ───────────── */

export type GraphAlgorithm = "none" | "bfs" | "dfs";
export type GraphFrame = {
  visited: string[];
  pending: string[];
  active?: string;
  edge?: [string, string];
  note: string;
};

export const graphTrace = (
  ids: string[],
  edges: { from: string; to: string }[],
  directed: boolean,
  start: string,
  mode: "bfs" | "dfs",
): GraphFrame[] => {
  const known = new Set(ids);
  const adj = new Map<string, string[]>(ids.map((id) => [id, []]));
  for (const e of edges) {
    if (!known.has(e.from) || !known.has(e.to)) continue;
    adj.get(e.from)!.push(e.to);
    if (!directed) adj.get(e.to)!.push(e.from);
  }
  const origin = known.has(start) ? start : ids[0];
  const visited: string[] = [];
  const frames: GraphFrame[] = [{ visited: [], pending: [origin], note: `Start at ${origin}` }];

  if (mode === "bfs") {
    const q = [origin];
    const seen = new Set(q);
    while (q.length) {
      const cur = q.shift()!;
      visited.push(cur);
      frames.push({ visited: [...visited], pending: [...q], active: cur, note: `Visit ${cur}` });
      for (const nb of adj.get(cur)!) {
        if (seen.has(nb)) continue;
        seen.add(nb);
        q.push(nb);
        frames.push({ visited: [...visited], pending: [...q], active: cur, edge: [cur, nb], note: `Queue ${nb}` });
      }
    }
  } else {
    const st = [origin];
    while (st.length) {
      const cur = st.pop()!;
      if (visited.includes(cur)) continue;
      visited.push(cur);
      frames.push({ visited: [...visited], pending: [...st], active: cur, note: `Visit ${cur}` });
      const nbs = adj.get(cur)!.filter((n) => !visited.includes(n));
      for (const nb of [...nbs].reverse()) st.push(nb);
      if (nbs.length) {
        frames.push({ visited: [...visited], pending: [...st], active: cur, edge: [cur, nbs[0]], note: `Go deeper from ${cur}` });
      }
    }
  }
  frames.push({ visited: [...visited], pending: [], note: "Every reachable node visited" });
  return frames;
};