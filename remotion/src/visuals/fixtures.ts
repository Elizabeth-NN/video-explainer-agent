/**
 * One realistic spec per visual. They double as regression fixtures
 * (every one must pass LibrarySchema) and as few-shot examples for the planner.
 */
export const FIXTURES: Record<string, unknown> = {
  array: { type: "array", title: "Bubble sort", values: [5, 2, 9, 1, 7, 3], algorithm: "bubble-sort", footnote: "Large values bubble to the end" },
  "array-search": { type: "array", title: "Binary search", values: [3, 8, 12, 19, 25, 31, 42], algorithm: "binary-search", target: 25 },
  "array-merge-overview": { type: "array", title: "Merge sort", values: [38, 27, 43, 3, 9, 82, 10], algorithm: "merge-sort", phase: "overview", footnote: "Illustrative values" },
  "array-merge-split": { type: "array", title: "Merge sort: split", values: [38, 27, 43, 3, 9, 82, 10], algorithm: "merge-sort", phase: "split", footnote: "Illustrative values" },
  "array-merge-merge": { type: "array", title: "Merge sort: merge", values: [38, 27, 43, 3, 9, 82, 10], algorithm: "merge-sort", phase: "merge", footnote: "Illustrative values" },
  "array-merge-sorted": { type: "array", title: "Merge sort: sorted", values: [38, 27, 43, 3, 9, 82, 10], algorithm: "merge-sort", phase: "sorted", footnote: "Illustrative values" },
  tree: { type: "tree", title: "Inserting into a BST", values: [8, 3, 10, 1, 6, 14, 4], algorithm: "insert" },
  "tree-traversal": { type: "tree", title: "In-order traversal", values: [8, 3, 10, 1, 6, 14, 4], algorithm: "inorder" },
  chain: { type: "chain", title: "A stack", kind: "stack", values: [4, 7, 2], ops: [{ op: "pop" }, { op: "push", value: 9 }] },
  "chain-list": { type: "chain", title: "A queue", kind: "queue", values: [1, 2, 3], ops: [{ op: "dequeue" }] },
  graph: {
    type: "graph", title: "Breadth-first search",
    nodes: ["A", "B", "C", "D", "E", "F"],
    edges: [{ from: "A", to: "B" }, { from: "A", to: "C" }, { from: "B", to: "D" }, { from: "C", to: "E" }, { from: "D", to: "F" }, { from: "E", to: "F" }],
    algorithm: "bfs", start: "A",
  },
  exchange: {
    type: "exchange", title: "An HTTP request", actors: ["Browser", "Server", "Database"],
    messages: [
      { from: "Browser", to: "Server", label: "GET /profile" },
      { from: "Server", to: "Database", label: "SELECT user" },
      { from: "Database", to: "Server", label: "row", reply: true },
      { from: "Server", to: "Browser", label: "200 OK + HTML", reply: true },
    ],
  },
  code: {
    type: "code", title: "What this loop does", language: "python",
    lines: ["total = 0", "for n in [1, 2, 3]:", "    total += n", "print(total)"],
    steps: [{ line: 1, note: "Start the total at zero" }, { line: 3, note: "Add each number to the total" }, { line: 4, note: "Print the final result", output: "6" }],
  },
  architecture: {
    type: "architecture", title: "A typical web stack",
    nodes: [
      { id: "c", label: "Browser", kind: "client" },
      { id: "cdn", label: "CDN", kind: "cdn" },
      { id: "lb", label: "Load balancer", kind: "loadbalancer" },
      { id: "a1", label: "API 1", kind: "server" },
      { id: "a2", label: "API 2", kind: "server" },
      { id: "cache", label: "Cache", kind: "cache" },
      { id: "db", label: "Database", kind: "database" },
    ],
    links: [
      { from: "c", to: "cdn" }, { from: "cdn", to: "lb" }, { from: "lb", to: "a1" }, { from: "lb", to: "a2" },
      { from: "a1", to: "cache" }, { from: "a2", to: "cache" }, { from: "cache", to: "db" },
    ],
    path: ["c", "cdn", "lb", "a1", "cache", "db"],
  },
  balancer: { type: "balancer", title: "Least connections", servers: 3, requests: 8, algorithm: "least-connections" },
  ring: { type: "ring", title: "Consistent hashing", nodes: ["A", "B", "C"], keys: ["user1", "user2", "user3", "user4", "user5", "user6"], addNode: "D" },
  cache: { type: "cache", title: "An LRU cache", capacity: 3, policy: "lru", accesses: ["A", "B", "C", "A", "D", "B", "A"] },
  pipeline: {
    type: "pipeline", title: "A CI/CD pipeline",
    stages: [
      { name: "Build", jobs: ["Compile"] },
      { name: "Test", jobs: ["Unit", "Lint"] },
      { name: "Package", jobs: ["Docker image"] },
      { name: "Deploy", jobs: ["Production"] },
    ],
  },
  "pipeline-fail": {
    type: "pipeline", title: "A failing build",
    stages: [{ name: "Build", jobs: ["Compile"] }, { name: "Test", jobs: ["Unit", "Lint"], fail: true }, { name: "Deploy", jobs: ["Production"] }],
  },
  deploy: { type: "deploy", title: "A canary release", strategy: "canary", instances: 4, from: "v1", to: "v2" },
  "deploy-bg": { type: "deploy", title: "Blue-green deploy", strategy: "blue-green", instances: 3, from: "v1", to: "v2" },
  table: {
    type: "table", title: "Selecting rows", name: "users", columns: ["id", "name", "age", "city"],
    rows: [[1, "Ana", 31, "Lima"], [2, "Bo", 25, "Oslo"], [3, "Cy", 40, "Rome"], [4, "Di", 28, "Cairo"]],
    query: { kind: "select", columns: ["name", "age"], where: { column: "age", op: ">", value: 27 } },
  },
  "table-update": {
    type: "table", title: "Updating rows", name: "users", columns: ["id", "name", "age"],
    rows: [[1, "Ana", 31], [2, "Bo", 25], [3, "Cy", 40]],
    query: { kind: "update", set: { column: "age", value: 26 }, where: { column: "name", op: "=", value: "Bo" } },
  },
  join: {
    type: "join", title: "A left join",
    left: { name: "users", columns: ["id", "name"], rows: [[1, "Ana"], [2, "Bo"], [3, "Cy"]] },
    right: { name: "orders", columns: ["user_id", "item"], rows: [[1, "Book"], [1, "Pen"], [3, "Cup"]] },
    on: { left: "id", right: "user_id" }, joinType: "left",
  },
  indexscan: { type: "indexscan", title: "Why indexes matter", values: [42, 7, 19, 88, 3, 56, 71, 25], target: 71 },
  replication: { type: "replication", title: "Async replication and failover", replicas: 2, mode: "async", writes: 3, failover: true },
  sharding: { type: "sharding", title: "Hash sharding", shards: 3, keys: ["ana", "ben", "cara", "dan", "eli", "fay", "gus", "hal"], strategy: "hash" },
  "sharding-range": { type: "sharding", title: "Range sharding", shards: 3, keys: ["alice", "amy", "adam", "bob", "carl", "zed", "yan", "mia"], strategy: "range" },
};
