/**
 * Writes the planner catalog to a text file the Python pipeline reads at startup,
 * so Gemini's instructions always match what Remotion can actually render.
 *
 *   cd remotion && npx tsx src/visuals/scripts/export-catalog.ts ../planner_catalog_cs.txt
 */
import { writeFileSync } from "node:fs";
import { PLANNER_CATALOG } from "../hints";

const out = process.argv[2] ?? "../planner_catalog_cs.txt";
writeFileSync(out, PLANNER_CATALOG + "\n", "utf8");
console.log(`wrote ${out} (${PLANNER_CATALOG.length} chars)`);
