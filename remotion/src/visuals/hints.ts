/**
 * One hint per library visual. The planner prompt is built from these, so the
 * schema Remotion validates and the instructions Gemini sees can't drift apart.
 * No React imports here: scripts/export-catalog.ts reads this file under plain Node.
 */
import { ARRAY_ALGORITHMS } from "./algorithms";

export const HINTS = {
  array:
    `array: a row of values. Use for arrays, sorting, searching, indexing.
  {"type":"array","values":[5,2,9,1,7],"algorithm":"bubble-sort","target":7}
  values: 2-10 non-negative numbers. algorithm: ${ARRAY_ALGORITHMS.join(" | ")}.
  target: only for the two searches. NEVER write the steps; the renderer computes them.
  phase (binary-search only): overview | midpoint | elimination | found | not-found, to show one stage per scene.`,

  tree:
    `tree: a binary search tree built by inserting values in order. Use for BSTs, tree traversal, heaps-as-trees, hierarchy of depth.
  {"type":"tree","values":[8,3,10,1,6,14],"algorithm":"inorder"}
  values: 1-9 distinct numbers. algorithm: none | insert | inorder | preorder | postorder | bfs. NEVER write the steps.`,

  chain:
    `chain: a stack, queue or linked list with operations. Use for push/pop, enqueue/dequeue, linked lists.
  {"type":"chain","kind":"stack","values":[4,7,2],"ops":[{"op":"pop"},{"op":"push","value":9}]}
  kind: stack | queue | linked-list. values: 0-6 numbers added first. ops (optional, max 8):
  push|pop (stack), enqueue|dequeue (queue), append|prepend|remove-first|remove-last (linked-list).`,

  graph:
    `graph: nodes and edges with optional BFS or DFS animation. Use for networks, graph traversal, dependencies, routes.
  {"type":"graph","nodes":["A","B","C","D"],"edges":[{"from":"A","to":"B"},{"from":"A","to":"C"},{"from":"B","to":"D"}],"algorithm":"bfs","start":"A"}
  nodes: 2-8 labels, max 6 characters each. edges: 1-14. directed: optional boolean. algorithm: none | bfs | dfs.`,

  exchange:
    `exchange: a message sequence between actors, drawn as a sequence diagram. Use for protocols, handshakes, API calls, auth flows, client-server talk.
  {"type":"exchange","actors":["Browser","Server"],"messages":[{"from":"Browser","to":"Server","label":"GET /page"},{"from":"Server","to":"Browser","label":"200 OK","reply":true}]}
  actors: 2-4 short names. messages: 1-7, in order, from/to must match an actor name. label max 28 characters. reply:true draws a dashed reply.`,

  code:
    `code: a short code listing with the current line highlighted step by step. Use for explaining what code does.
  {"type":"code","language":"python","lines":["total = 0","for n in [1, 2, 3]:","    total += n","print(total)"],"steps":[{"line":1,"note":"Start at zero"},{"line":3,"note":"Add each number"},{"line":4,"note":"Print the result","output":"6"}]}
  lines: 2-10 lines, max 44 characters each. steps: 1-8, line is 1-based. output: ONLY text the narration states. Never invent output.`,

  architecture:
    `architecture: boxes for infrastructure components laid out in tiers, with links and an optional animated request path. Use for system design, "how X is built", request flow through a stack.
  {"type":"architecture","nodes":[{"id":"c","label":"Browser","kind":"client"},{"id":"lb","label":"Load balancer","kind":"loadbalancer"},{"id":"api","label":"API","kind":"server"},{"id":"db","label":"Database","kind":"database"}],"links":[{"from":"c","to":"lb"},{"from":"lb","to":"api"},{"from":"api","to":"db"}],"path":["c","lb","api","db"]}
  kind: client | cdn | loadbalancer | server | service | cache | database | queue | storage | worker | dns | firewall | monitor.
  nodes: 2-10, label max 14 chars. links: 1-14. tier (0-5) is optional, it is worked out from the links. path: node ids in order, max 8.`,

  balancer:
    `balancer: requests spread across servers by a load-balancing algorithm. The renderer simulates it.
  {"type":"balancer","servers":3,"requests":8,"algorithm":"least-connections"}
  servers: 2-5. requests: 3-12. algorithm: round-robin | least-connections | ip-hash | weighted-round-robin. weights: optional list, one per server.`,

  ring:
    `ring: consistent hashing. Servers and keys are hashed onto a ring; adding a server moves only a few keys.
  {"type":"ring","nodes":["A","B","C"],"keys":["user1","user2","user3","user4","user5"],"addNode":"D"}
  nodes: 2-5 short names. keys: 3-10 short names. addNode: optional, shows what moves. vnodes: optional 1-3.`,

  cache:
    `cache: a fixed-size cache handling a sequence of reads, showing hits, misses and evictions. The renderer simulates it.
  {"type":"cache","capacity":3,"policy":"lru","accesses":["A","B","C","A","D","B"]}
  capacity: 2-5. policy: lru | fifo | lfu. accesses: 4-14 short keys.`,

  pipeline:
    `pipeline: a CI/CD pipeline whose stages run one after another.
  {"type":"pipeline","stages":[{"name":"Build","jobs":["Compile"]},{"name":"Test","jobs":["Unit","Lint"]},{"name":"Deploy","jobs":["Release"],"fail":false}]}
  stages: 3-6, name max 10 chars. jobs: up to 3 per stage. fail:true makes that stage fail and later stages skip. Use it only if the narration says something fails.`,

  deploy:
    `deploy: a deployment strategy shown as instances and a traffic split. The renderer computes every step.
  {"type":"deploy","strategy":"canary","instances":4,"from":"v1","to":"v2"}
  strategy: rolling | blue-green | canary. instances: 2-6. from/to: version labels, max 8 chars.`,

  table:
    `table: a database table, optionally with one SQL query that is highlighted and applied. The renderer computes the result and writes the SQL.
  {"type":"table","name":"users","columns":["id","name","age"],"rows":[[1,"Ana",31],[2,"Bo",25],[3,"Cy",40]],"query":{"kind":"select","columns":["name"],"where":{"column":"age","op":">","value":30}}}
  columns: 2-5. rows: 1-7, each as long as columns. query is optional. kind: select | update | delete | insert.
  select: optional columns and where. update: set {column,value} and optional where. delete: optional where. insert: values (one per column).
  where.op: = | != | > | < | >= | <=.`,

  join:
    `join: a SQL join of two small tables. The renderer computes the result rows.
  {"type":"join","left":{"name":"users","columns":["id","name"],"rows":[[1,"Ana"],[2,"Bo"]]},"right":{"name":"orders","columns":["user_id","item"],"rows":[[1,"Book"],[1,"Pen"]]},"on":{"left":"id","right":"user_id"},"joinType":"inner"}
  Each table: max 3 columns, max 4 rows. joinType: inner | left. on.left/on.right must be column names.`,

  indexscan:
    `indexscan: why a database index is faster than scanning every row. Both searches run side by side with a counter.
  {"type":"indexscan","values":[42,7,19,88,3,56,71,25],"target":71}
  values: 6-12 distinct numbers (row ids). target: one of the values.`,

  replication:
    `replication: a primary database copying writes to replicas, sync or async, with an optional failover.
  {"type":"replication","replicas":2,"mode":"async","writes":3,"failover":true}
  replicas: 1-3. mode: sync | async. writes: 2-4. failover:true makes the primary fail at the end, and the renderer shows whether acknowledged writes were lost.`,

  sharding:
    `sharding: keys routed to database shards by hash or by range.
  {"type":"sharding","shards":3,"keys":["alice","bob","carol","dave","erin","frank"],"strategy":"hash"}
  shards: 2-4. keys: 4-10 short lowercase names. strategy: hash | range (range splits by first letter).`,
} as const;

export type HintKey = keyof typeof HINTS;

export const PLANNER_CATALOG = Object.values(HINTS).map((h) => `- ${h}`).join("\n");