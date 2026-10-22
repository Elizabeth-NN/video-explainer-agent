/**
 * Writes the planner catalog to a text file the Python pipeline reads at startup,
 * plus a JSON list of the registered library types next to it, so Gemini's
 * instructions and Python's library-type check always match what Remotion can
 * actually render.
 *
 *   cd remotion && npx tsx src/visuals/export_catalog.ts ../planner_catalog.txt
 */
import { writeFileSync } from "node:fs";
import path from "node:path";
import { HINTS, PLANNER_CATALOG } from "./hints";

const out = process.argv[2] ?? "../planner_catalog.txt";
writeFileSync(out, PLANNER_CATALOG + "\n", "utf8");
console.log(`wrote ${out} (${PLANNER_CATALOG.length} chars)`);

const typesOut = path.join(
  path.dirname(out),
  `${path.basename(out, path.extname(out))}.json`,
);
const types = Object.keys(HINTS);
writeFileSync(typesOut, JSON.stringify({ types }, null, 2) + "\n", "utf8");
console.log(`wrote ${typesOut} (${types.length} types)`);
