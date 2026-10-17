/**
 * One hint per library visual. The planner prompt is built from these, so the
 * schema Remotion validates and the instructions Gemini sees can't drift apart.
 * No React imports here: scripts/export-catalog.ts reads this file under plain Node.
 */
export const HINTS = {
  array:
    `array: a row of values. Use for arrays, sorting, searching, indexing.
  {"type":"array","values":[5,2,9,1,7],"algorithm":"bubble-sort","target":7}
  values: 2-10 non-negative numbers. algorithm: none | bubble-sort | selection-sort | insertion-sort | binary-search | linear-search.
  target: only for the two searches. NEVER write the steps; the renderer computes them.`,

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
} as const;

export type HintKey = keyof typeof HINTS;

export const PLANNER_CATALOG = Object.values(HINTS).map((h) => `- ${h}`).join("\n");
