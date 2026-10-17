/**
 * Deterministic traces for system design, DevOps and database visuals.
 * Same rule as algorithms.ts: the planner supplies inputs, this file computes the steps.
 * Pure functions, no React. Checked by systems.check.ts.
 */

/** FNV-1a. Deterministic, so a video always shows the same routing. */
export const fnv = (s: string): number => {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
};
export const hash360 = (s: string): number => fnv(s) % 360;

/* ───────────── load balancer ───────────── */

export type BalancerAlgo = "round-robin" | "least-connections" | "ip-hash" | "weighted-round-robin";
export type BalancerFrame = {
  loads: number[];
  served: number[];
  req: number;
  target?: number;
  client?: string;
  note: string;
};

const DEFAULT_COSTS = [3, 1, 4, 1, 5, 2, 3, 1, 4, 2, 3, 1];

/** Request i arrives each tick; a request with cost c stays active for c ticks. */
export const balancerTrace = (
  servers: number,
  requests: number,
  algo: BalancerAlgo,
  weights?: number[],
  costs?: number[],
): BalancerFrame[] => {
  const costList = costs && costs.length ? costs : DEFAULT_COSTS;
  const active: number[][] = Array.from({ length: servers }, () => []);
  const served: number[] = Array(servers).fill(0);
  const w = weights && weights.length === servers ? weights.map((x) => Math.max(1, Math.round(x))) : Array(servers).fill(1);
  const wheel = w.flatMap((x, i) => Array<number>(x).fill(i));
  const frames: BalancerFrame[] = [
    { loads: Array(servers).fill(0), served: [...served], req: 0, note: "Servers are idle" },
  ];

  for (let i = 0; i < requests; i++) {
    for (const a of active) {
      for (let k = a.length - 1; k >= 0; k--) {
        a[k] -= 1;
        if (a[k] <= 0) a.splice(k, 1);
      }
    }
    const client = `10.0.0.${(i * 37 + 11) % 250}`;
    let t = 0;
    let note = "";
    switch (algo) {
      case "round-robin":
        t = i % servers;
        note = `Request ${i + 1} goes to server ${t + 1}, the next in turn`;
        break;
      case "weighted-round-robin":
        t = wheel[i % wheel.length];
        note = `Request ${i + 1} goes to server ${t + 1} (weight ${w[t]})`;
        break;
      case "least-connections": {
        t = active.reduce((best, a, idx) => (a.length < active[best].length ? idx : best), 0);
        note = `Server ${t + 1} has the fewest active connections (${active[t].length})`;
        break;
      }
      case "ip-hash":
        t = fnv(client) % servers;
        note = `${client} always hashes to server ${t + 1}`;
        break;
    }
    active[t].push(costList[i % costList.length]);
    served[t]++;
    frames.push({ loads: active.map((a) => a.length), served: [...served], req: i + 1, target: t, client, note });
  }
  return frames;
};

/* ───────────── consistent hashing ring ───────────── */

export type RingPoint = { name: string; pos: number };
export type RingKey = { name: string; pos: number; owner: string };
export type RingFrame = {
  points: RingPoint[];
  keys: RingKey[];
  active?: string;
  moved: string[];
  added?: string;
  note: string;
};

const pointsFor = (name: string, vnodes: number): RingPoint[] =>
  Array.from({ length: vnodes }, (_, k) => ({ name, pos: hash360(`${name}#${k}`) }));

/** A key belongs to the first server point at or after its position, going clockwise. */
export const ringOwner = (points: RingPoint[], pos: number): string => {
  const sorted = [...points].sort((a, b) => a.pos - b.pos);
  return (sorted.find((p) => p.pos >= pos) ?? sorted[0]).name;
};

export const ringTrace = (nodes: string[], keys: string[], addNode?: string, vnodes = 1): RingFrame[] => {
  const points = nodes.flatMap((n) => pointsFor(n, vnodes));
  const owners = (pts: RingPoint[], upTo = keys.length): RingKey[] =>
    keys.slice(0, upTo).map((k) => {
      const pos = hash360(k);
      return { name: k, pos, owner: ringOwner(pts, pos) };
    });

  const frames: RingFrame[] = [
    { points, keys: [], moved: [], note: "Servers sit on a ring at the hash of their name" },
  ];
  keys.forEach((k, i) => {
    const placed = owners(points, i + 1);
    frames.push({
      points, keys: placed, active: k, moved: [],
      note: `${k} belongs to the first server clockwise: ${placed[i].owner}`,
    });
  });

  if (addNode && !nodes.includes(addNode)) {
    const before = owners(points);
    const after2 = [...points, ...pointsFor(addNode, vnodes)];
    const after = owners(after2);
    const moved = after.filter((k, i) => k.owner !== before[i].owner).map((k) => k.name);
    frames.push({
      points: after2, keys: after, moved, added: addNode,
      note: `Add ${addNode}: only ${moved.length} of ${keys.length} keys move`,
    });
  }
  return frames;
};

/* ───────────── cache ───────────── */

export type CachePolicy = "lru" | "fifo" | "lfu";
export type CacheFrame = {
  key?: string;
  slots: string[];
  freqs: number[];
  victim?: number;
  hit?: boolean;
  evicted?: string;
  hits: number;
  misses: number;
  note: string;
};

export const cacheTrace = (capacity: number, policy: CachePolicy, accesses: string[]): CacheFrame[] => {
  const slots: string[] = [];
  const freq = new Map<string, number>();
  let hits = 0;
  let misses = 0;

  /** Index in `slots` of the entry that would be evicted next. */
  const victimIndex = (): number | undefined => {
    if (!slots.length) return undefined;
    if (policy !== "lfu") return 0;
    let best = 0;
    slots.forEach((k, i) => {
      if ((freq.get(k) ?? 0) < (freq.get(slots[best]) ?? 0)) best = i;
    });
    return best;
  };
  const snap = (extra: Partial<CacheFrame> & { note: string }): CacheFrame => ({
    slots: [...slots], freqs: slots.map((k) => freq.get(k) ?? 0), victim: victimIndex(), hits, misses, ...extra,
  });

  const frames: CacheFrame[] = [snap({ note: `Empty cache with room for ${capacity} items` })];
  for (const key of accesses) {
    const at = slots.indexOf(key);
    if (at >= 0) {
      hits++;
      freq.set(key, (freq.get(key) ?? 0) + 1);
      if (policy === "lru") {
        slots.splice(at, 1);
        slots.push(key);
      }
      frames.push(snap({ key, hit: true, note: `${key} is in the cache: hit` }));
      continue;
    }
    misses++;
    let evicted: string | undefined;
    if (slots.length >= capacity) {
      const v = victimIndex()!;
      evicted = slots.splice(v, 1)[0];
      freq.delete(evicted);
    }
    slots.push(key);
    freq.set(key, 1);
    frames.push(
      snap({
        key, hit: false, evicted,
        note: evicted ? `${key} is missing: miss, so evict ${evicted}` : `${key} is missing: miss, so load it`,
      }),
    );
  }
  return frames;
};

/* ───────────── deployments ───────────── */

export type DeployStrategy = "rolling" | "blue-green" | "canary";
export type DeployInst = { v: 1 | 2; st: "ready" | "starting" | "idle" | "retired"; row: 0 | 1 };
export type DeployFrame = { instances: DeployInst[]; traffic: [number, number]; note: string };

const share = (insts: DeployInst[]): [number, number] => {
  const r1 = insts.filter((i) => i.v === 1 && i.st === "ready").length;
  const r2 = insts.filter((i) => i.v === 2 && i.st === "ready").length;
  const total = r1 + r2 || 1;
  const p2 = Math.round((r2 / total) * 100);
  return [100 - p2, p2];
};

export const deployTrace = (strategy: DeployStrategy, n: number, from = "v1", to = "v2"): DeployFrame[] => {
  const mk = (v: 1 | 2, st: DeployInst["st"], row: 0 | 1 = 0): DeployInst => ({ v, st, row });
  const clone = (xs: DeployInst[]) => xs.map((x) => ({ ...x }));

  if (strategy === "rolling") {
    const insts = Array.from({ length: n }, () => mk(1, "ready"));
    const frames: DeployFrame[] = [{ instances: clone(insts), traffic: share(insts), note: `All ${n} instances run ${from}` }];
    for (let i = 0; i < n; i++) {
      insts[i] = mk(2, "starting");
      frames.push({ instances: clone(insts), traffic: share(insts), note: `Replace instance ${i + 1}: start ${to}` });
      insts[i] = mk(2, "ready");
      frames.push({ instances: clone(insts), traffic: share(insts), note: `${to} is healthy, move on to the next` });
    }
    frames.push({ instances: clone(insts), traffic: [0, 100], note: `Rollout complete: every instance runs ${to}` });
    return frames;
  }

  if (strategy === "canary") {
    const insts = Array.from({ length: n }, () => mk(1, "ready"));
    const frames: DeployFrame[] = [{ instances: clone(insts), traffic: [100, 0], note: `All traffic goes to ${from}` }];
    const withCanary = [...insts, mk(2, "starting")];
    frames.push({ instances: clone(withCanary), traffic: [100, 0], note: `Start one ${to} canary` });
    withCanary[n] = mk(2, "ready");
    for (const pct of [5, 25, 50]) {
      frames.push({
        instances: clone(withCanary), traffic: [100 - pct, pct],
        note: `Send ${pct}% of traffic to ${to} and watch the metrics`,
      });
    }
    const done = Array.from({ length: n }, () => mk(2, "ready"));
    frames.push({ instances: done, traffic: [0, 100], note: `Healthy: promote ${to} to everyone` });
    return frames;
  }

  const blue = Array.from({ length: n }, () => mk(1, "ready", 0));
  const green = Array.from({ length: n }, () => mk(2, "starting", 1));
  const frames: DeployFrame[] = [{ instances: clone(blue), traffic: [100, 0], note: `Blue runs ${from} and serves everyone` }];
  frames.push({ instances: clone([...blue, ...green]), traffic: [100, 0], note: `Deploy ${to} to a separate green environment` });
  const idleGreen = green.map((g) => ({ ...g, st: "idle" as const }));
  frames.push({ instances: clone([...blue, ...idleGreen]), traffic: [100, 0], note: "Green is tested while taking no traffic" });
  const liveGreen = green.map((g) => ({ ...g, st: "ready" as const }));
  const idleBlue = blue.map((b) => ({ ...b, st: "idle" as const }));
  frames.push({ instances: clone([...idleBlue, ...liveGreen]), traffic: [0, 100], note: "Switch the router: all traffic moves at once" });
  frames.push({ instances: clone([...idleBlue, ...liveGreen]), traffic: [0, 100], note: "Blue stays on standby, so rollback is one switch" });
  return frames;
};

/* ───────────── CI/CD pipeline ───────────── */

export type PipeStatus = "pending" | "running" | "pass" | "fail" | "skipped";
export type PipeFrame = { status: PipeStatus[]; note: string };

export const pipelineTrace = (stages: { name: string; fail?: boolean }[]): PipeFrame[] => {
  const status: PipeStatus[] = stages.map(() => "pending");
  const frames: PipeFrame[] = [{ status: [...status], note: "Code is pushed and the pipeline starts" }];
  for (let i = 0; i < stages.length; i++) {
    status[i] = "running";
    frames.push({ status: [...status], note: `Running ${stages[i].name}` });
    if (stages[i].fail) {
      status[i] = "fail";
      for (let j = i + 1; j < stages.length; j++) status[j] = "skipped";
      frames.push({ status: [...status], note: `${stages[i].name} failed, so the pipeline stops here` });
      return frames;
    }
    status[i] = "pass";
    frames.push({ status: [...status], note: `${stages[i].name} passed` });
  }
  frames.push({ status: [...status], note: "Every stage passed: the change is live" });
  return frames;
};

/* ───────────── tables and SQL ───────────── */

export type Cell = string | number;
export type Where = { column: string; op: "=" | "!=" | ">" | "<" | ">=" | "<="; value: Cell };
export type Query = {
  kind: "select" | "update" | "delete" | "insert";
  where?: Where;
  columns?: string[];
  set?: { column: string; value: Cell };
  values?: Cell[];
};
export type TableFrame = {
  rows: Cell[][];
  matched: number[];
  dimOthers: boolean;
  dimCols: string[];
  changed: [number, number][];
  danger: boolean;
  added?: number;
  note: string;
};

const asNum = (v: Cell): number =>
  typeof v === "number" ? v : v.trim() !== "" && !Number.isNaN(Number(v)) ? Number(v) : NaN;

export const compare = (a: Cell, op: Where["op"], b: Cell): boolean => {
  const na = asNum(a);
  const nb = asNum(b);
  const c = !Number.isNaN(na) && !Number.isNaN(nb)
    ? na - nb
    : String(a).toLowerCase().localeCompare(String(b).toLowerCase());
  switch (op) {
    case "=": return c === 0;
    case "!=": return c !== 0;
    case ">": return c > 0;
    case "<": return c < 0;
    case ">=": return c >= 0;
    default: return c <= 0;
  }
};

const lit = (v: Cell): string => (Number.isNaN(asNum(v)) ? `'${v}'` : String(v));
const whereSql = (w?: Where) => (w ? ` WHERE ${w.column} ${w.op} ${lit(w.value)}` : "");

export const sqlOf = (table: string, q: Query): string => {
  switch (q.kind) {
    case "select": return `SELECT ${q.columns?.length ? q.columns.join(", ") : "*"} FROM ${table}${whereSql(q.where)}`;
    case "update": return `UPDATE ${table} SET ${q.set?.column ?? "?"} = ${q.set ? lit(q.set.value) : "?"}${whereSql(q.where)}`;
    case "delete": return `DELETE FROM ${table}${whereSql(q.where)}`;
    default: return `INSERT INTO ${table} VALUES (${(q.values ?? []).map(lit).join(", ")})`;
  }
};

export const tableTrace = (cols: string[], rowsIn: Cell[][], q?: Query): TableFrame[] => {
  const rows = rowsIn.map((r) => cols.map((_, i) => r[i] ?? "NULL"));
  const ci = (c: string) => cols.findIndex((x) => x.toLowerCase() === c.toLowerCase());
  const hit = (r: Cell[]) => {
    if (!q?.where) return true;
    const i = ci(q.where.column);
    return i >= 0 && compare(r[i], q.where.op, q.where.value);
  };
  const base: TableFrame = {
    rows, matched: [], dimOthers: false, dimCols: [], changed: [], danger: false, note: "The table before the query",
  };
  if (!q) return [base];

  const frames: TableFrame[] = [base];
  const idxs = rows.map((r, i) => (hit(r) ? i : -1)).filter((i) => i >= 0);

  if (q.kind === "insert") {
    const row = cols.map((_, i) => q.values?.[i] ?? "NULL");
    frames.push({ ...base, rows: [...rows, row], added: rows.length, note: "Insert one new row at the end" });
    return frames;
  }

  if (q.where) {
    frames.push({
      ...base, matched: idxs, danger: q.kind === "delete",
      note: `${idxs.length} row${idxs.length === 1 ? "" : "s"} match the WHERE clause`,
    });
  }

  if (q.kind === "select") {
    const keep = q.columns?.length ? q.columns.map((c) => c.toLowerCase()) : null;
    frames.push({
      ...base, matched: idxs, dimOthers: true,
      dimCols: keep ? cols.filter((c) => !keep.includes(c.toLowerCase())) : [],
      note: `Returns ${idxs.length} row${idxs.length === 1 ? "" : "s"}`,
    });
  } else if (q.kind === "update") {
    const c = q.set ? ci(q.set.column) : -1;
    const next = rows.map((r, i) => (c >= 0 && idxs.includes(i) ? r.map((v, j) => (j === c ? q.set!.value : v)) : r));
    frames.push({
      ...base, rows: next, matched: idxs, changed: c >= 0 ? idxs.map((i) => [i, c] as [number, number]) : [],
      note: `Updated ${idxs.length} row${idxs.length === 1 ? "" : "s"}`,
    });
  } else {
    frames.push({
      ...base, rows: rows.filter((_, i) => !idxs.includes(i)),
      note: `Deleted ${idxs.length} row${idxs.length === 1 ? "" : "s"}`,
    });
  }
  return frames;
};

/* ───────────── joins ───────────── */

export type JoinFrame = { leftHi?: number; rightHi: number[]; result: Cell[][]; note: string };

export const joinColumns = (ln: string, lc: string[], rn: string, rc: string[]): string[] => {
  const dupes = new Set(lc.filter((c) => rc.includes(c)));
  return [...lc.map((c) => (dupes.has(c) ? `${ln}.${c}` : c)), ...rc.map((c) => (dupes.has(c) ? `${rn}.${c}` : c))];
};

export const joinTrace = (
  left: { cols: string[]; rows: Cell[][] },
  right: { cols: string[]; rows: Cell[][] },
  lcol: string,
  rcol: string,
  type: "inner" | "left",
): JoinFrame[] => {
  const li = Math.max(0, left.cols.findIndex((c) => c.toLowerCase() === lcol.toLowerCase()));
  const ri = Math.max(0, right.cols.findIndex((c) => c.toLowerCase() === rcol.toLowerCase()));
  const pad = (r: Cell[], n: number) => Array.from({ length: n }, (_, i) => r[i] ?? "NULL");
  const result: Cell[][] = [];
  const frames: JoinFrame[] = [{ rightHi: [], result: [], note: "Two tables share a key" }];

  left.rows.forEach((lr, i) => {
    const lrow = pad(lr, left.cols.length);
    const matches = right.rows
      .map((rr, k) => (String(rr[ri]).toLowerCase() === String(lrow[li]).toLowerCase() ? k : -1))
      .filter((k) => k >= 0);
    if (matches.length) {
      for (const k of matches) result.push([...lrow, ...pad(right.rows[k], right.cols.length)]);
      frames.push({
        leftHi: i, rightHi: matches, result: result.map((r) => [...r]),
        note: `${lrow[li]} matches ${matches.length} row${matches.length === 1 ? "" : "s"}`,
      });
    } else if (type === "left") {
      result.push([...lrow, ...Array<Cell>(right.cols.length).fill("NULL")]);
      frames.push({ leftHi: i, rightHi: [], result: result.map((r) => [...r]), note: `${lrow[li]} has no match: kept, with NULLs` });
    } else {
      frames.push({ leftHi: i, rightHi: [], result: result.map((r) => [...r]), note: `${lrow[li]} has no match: dropped` });
    }
  });
  frames.push({ rightHi: [], result: result.map((r) => [...r]), note: `Result: ${result.length} row${result.length === 1 ? "" : "s"}` });
  return frames;
};

/* ───────────── replication ───────────── */

export type ReplRole = "primary" | "replica" | "down";
export type ReplFrame = { applied: number[]; role: ReplRole[]; acked: number; arrow?: [number, number]; note: string };

export const replicationTrace = (
  replicas: number,
  mode: "sync" | "async",
  writes: number,
  failover: boolean,
): ReplFrame[] => {
  const n = replicas + 1;
  const applied: number[] = Array(n).fill(0);
  const role: ReplRole[] = Array.from({ length: n }, (_, i) => (i === 0 ? "primary" : "replica"));
  let acked = 0;
  const snap = (note: string, arrow?: [number, number]): ReplFrame => ({
    applied: [...applied], role: [...role], acked, arrow, note,
  });
  const frames: ReplFrame[] = [snap("A primary and its replicas start in sync")];

  for (let k = 1; k <= writes; k++) {
    applied[0] = k;
    if (mode === "async") {
      acked = k;
      frames.push(snap(`Write ${k} commits on the primary and is acknowledged at once`));
    } else {
      frames.push(snap(`Write ${k} is applied on the primary, not acknowledged yet`));
    }
    const lagging = mode === "async" && failover && k === writes;
    if (lagging) {
      frames.push(snap(`Replication lag: write ${k} hasn't reached the replicas yet`));
      continue;
    }
    for (let r = 1; r < n; r++) {
      applied[r] = k;
      frames.push(snap(`Replica ${r} copies write ${k}`, [0, r]));
    }
    if (mode === "sync") {
      acked = k;
      frames.push(snap(`Write ${k} is acknowledged after every replica confirmed`));
    }
  }

  if (failover) {
    role[0] = "down";
    frames.push(snap("The primary fails"));
    role[1] = "primary";
    const lost = acked - applied[1];
    frames.push(
      snap(
        lost > 0
          ? `Replica 1 is promoted, but ${lost} acknowledged write${lost === 1 ? " is" : "s are"} lost`
          : "Replica 1 is promoted, and no acknowledged write is lost",
      ),
    );
  }
  return frames;
};

/* ───────────── sharding ───────────── */

export type ShardStrategy = "hash" | "range";
export type ShardFrame = { shards: string[][]; active?: { key: string; shard: number }; note: string };

const letterIndex = (key: string): number => {
  const c = key.trim().toLowerCase().charCodeAt(0) - 97;
  return c >= 0 && c < 26 ? c : 0;
};

export const shardOf = (key: string, shards: number, strategy: ShardStrategy): number =>
  strategy === "hash"
    ? fnv(key) % shards
    : Math.min(shards - 1, Math.floor(letterIndex(key) / Math.ceil(26 / shards)));

export const rangeLabels = (shards: number): string[] => {
  const per = Math.ceil(26 / shards);
  return Array.from({ length: shards }, (_, b) => {
    const from = b * per;
    const to = Math.min(25, (b + 1) * per - 1);
    return `${String.fromCharCode(65 + from)}–${String.fromCharCode(65 + to)}`;
  });
};

export const shardTrace = (shards: number, keys: string[], strategy: ShardStrategy): ShardFrame[] => {
  const buckets: string[][] = Array.from({ length: shards }, () => []);
  const frames: ShardFrame[] = [
    {
      shards: buckets.map((b) => [...b]),
      note: strategy === "hash" ? `Each key goes to hash(key) mod ${shards}` : "Each key goes to the shard that owns its first letter",
    },
  ];
  for (const key of keys) {
    const s = shardOf(key, shards, strategy);
    buckets[s].push(key);
    frames.push({ shards: buckets.map((b) => [...b]), active: { key, shard: s }, note: `${key} goes to shard ${s + 1}` });
  }
  const biggest = Math.max(...buckets.map((b) => b.length));
  frames.push({
    shards: buckets.map((b) => [...b]),
    note: `The busiest shard holds ${biggest} of ${keys.length} keys`,
  });
  return frames;
};
