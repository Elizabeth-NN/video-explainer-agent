/** Run: npx tsx src/visuals/systems.check.ts   (exits non-zero on failure) */
import assert from "node:assert/strict";
import {
  balancerTrace, cacheTrace, deployTrace, joinTrace, pipelineTrace, rangeLabels, replicationTrace,
  ringTrace, shardOf, shardTrace, sqlOf, tableTrace,
} from "./systems";

const last = <T,>(xs: T[]) => xs[xs.length - 1];

/* load balancer */
assert.deepEqual(last(balancerTrace(3, 9, "round-robin")).served, [3, 3, 3], "round robin is even");
assert.deepEqual(last(balancerTrace(3, 5, "weighted-round-robin", [3, 1, 1])).served, [3, 1, 1], "weights respected");
{
  const f = balancerTrace(3, 12, "least-connections");
  assert.equal(last(f).served.reduce((a, b) => a + b, 0), 12, "every request is served");
  for (let i = 1; i < f.length; i++) {
    const t = f[i].target!;
    // the chosen server never has more load than any other one, measured before this request landed
    const before = f[i].loads.map((l, k) => (k === t ? l - 1 : l));
    assert.ok(before.every((l) => l >= before[t]), `least-connections picks the least loaded (step ${i})`);
  }
}
assert.deepEqual(
  balancerTrace(4, 6, "ip-hash").map((f) => f.target),
  balancerTrace(4, 6, "ip-hash").map((f) => f.target),
  "ip-hash is deterministic",
);

/* consistent hashing */
{
  const keys = ["u1", "u2", "u3", "u4", "u5", "u6", "u7", "u8"];
  const f = ringTrace(["A", "B", "C"], keys, "D");
  const end = last(f);
  assert.equal(end.added, "D");
  for (const name of end.moved) {
    assert.equal(end.keys.find((k) => k.name === name)!.owner, "D", "a moved key can only move to the new node");
  }
  assert.ok(end.moved.length < keys.length, "not every key moves");
}

/* cache */
{
  const seq = ["A", "B", "C", "A", "D"];
  const lru = last(cacheTrace(3, "lru", seq));
  assert.deepEqual(lru.slots, ["C", "A", "D"], "lru evicts B");
  assert.equal(lru.evicted, "B");
  assert.equal(lru.hits, 1);
  assert.equal(lru.misses, 4);
  const fifo = last(cacheTrace(3, "fifo", seq));
  assert.deepEqual(fifo.slots, ["B", "C", "D"], "fifo evicts A");
  const lfu = last(cacheTrace(3, "lfu", seq));
  assert.deepEqual(lfu.slots, ["A", "C", "D"], "lfu keeps the frequently used A");
}

/* deployments */
for (const strategy of ["rolling", "canary", "blue-green"] as const) {
  const f = deployTrace(strategy, 3);
  for (const fr of f) assert.equal(fr.traffic[0] + fr.traffic[1], 100, `${strategy}: traffic sums to 100`);
  assert.deepEqual(last(f).traffic, [0, 100], `${strategy}: ends on v2`);
  assert.ok(f.every((fr) => fr.instances.some((i) => i.st === "ready")), `${strategy}: never fully down`);
}
assert.ok(last(deployTrace("canary", 3)).instances.every((i) => i.v === 2), "canary promotes everyone");

/* pipeline */
assert.deepEqual(
  last(pipelineTrace([{ name: "a" }, { name: "b", fail: true }, { name: "c" }, { name: "d" }])).status,
  ["pass", "fail", "skipped", "skipped"],
  "a failure skips later stages",
);
assert.deepEqual(last(pipelineTrace([{ name: "a" }, { name: "b" }, { name: "c" }])).status, ["pass", "pass", "pass"]);

/* SQL */
{
  const cols = ["id", "name", "age"];
  const rows = [[1, "Ana", 31], [2, "Bo", 25], [3, "Cy", 40]];
  const sel = tableTrace(cols, rows, { kind: "select", columns: ["name"], where: { column: "age", op: ">", value: 30 } });
  assert.deepEqual(last(sel).matched, [0, 2], "select where age > 30");
  assert.deepEqual(last(sel).dimCols, ["id", "age"], "unselected columns are dimmed");
  const del = tableTrace(cols, rows, { kind: "delete", where: { column: "name", op: "=", value: "bo" } });
  assert.equal(last(del).rows.length, 2, "delete is case-insensitive and removes the row");
  const upd = tableTrace(cols, rows, { kind: "update", set: { column: "age", value: 99 }, where: { column: "id", op: "<=", value: 2 } });
  assert.deepEqual(last(upd).rows.map((r) => r[2]), [99, 99, 40], "update changes only matching rows");
  assert.equal(last(tableTrace(cols, rows, { kind: "insert", values: [4, "Di"] })).rows[3][2], "NULL", "insert pads with NULL");
  assert.equal(
    sqlOf("users", { kind: "select", columns: ["name"], where: { column: "age", op: ">", value: 30 } }),
    "SELECT name FROM users WHERE age > 30",
  );
  assert.equal(sqlOf("users", { kind: "delete", where: { column: "name", op: "=", value: "Bo" } }), "DELETE FROM users WHERE name = 'Bo'");
}

/* joins */
{
  const left = { cols: ["id", "name"], rows: [[1, "Ana"], [2, "Bo"], [3, "Cy"]] };
  const right = { cols: ["user_id", "item"], rows: [[1, "Book"], [1, "Pen"], [3, "Cup"]] };
  assert.equal(last(joinTrace(left, right, "id", "user_id", "inner")).result.length, 3, "inner join drops unmatched");
  const lj = last(joinTrace(left, right, "id", "user_id", "left")).result;
  assert.equal(lj.length, 4, "left join keeps unmatched");
  assert.deepEqual(lj[2], [2, "Bo", "NULL", "NULL"]);
}

/* replication */
{
  const a = last(replicationTrace(2, "async", 3, true));
  assert.match(a.note, /1 acknowledged write is lost/, "async failover loses the last acknowledged write");
  const s = last(replicationTrace(2, "sync", 3, true));
  assert.match(s.note, /no acknowledged write is lost/, "sync failover loses nothing");
  assert.equal(last(replicationTrace(2, "sync", 3, false)).acked, 3);
}

/* sharding */
{
  const keys = ["alice", "bob", "carol", "dave", "erin", "zed"];
  for (const strat of ["hash", "range"] as const) {
    const end = last(shardTrace(3, keys, strat));
    assert.equal(end.shards.flat().length, keys.length, `${strat}: every key placed once`);
  }
  assert.equal(shardOf("alice", 2, "range"), 0);
  assert.equal(shardOf("zed", 2, "range"), 1);
  assert.deepEqual(rangeLabels(2), ["A–M", "N–Z"]);
  assert.equal(shardOf("alice", 4, "hash"), shardOf("alice", 4, "hash"), "hash is stable");
}

console.log("all systems checks passed");
