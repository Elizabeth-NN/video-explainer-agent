/** Run: npx tsx src/visuals/fixtures.check.ts
 *  Every fixture AND every JSON example inside the planner hints must pass LibrarySchema,
 *  so the instructions Gemini sees can never drift from what Remotion accepts. */
import assert from "node:assert/strict";
import { FIXTURES } from "./fixtures";
import { HINTS } from "./hints";
import { LibrarySchema, LIBRARY } from "./index";

let checked = 0;
for (const [name, spec] of Object.entries(FIXTURES)) {
  const r = LibrarySchema.safeParse(spec);
  assert.ok(r.success, `fixture "${name}" fails the schema: ${r.success ? "" : JSON.stringify(r.error.issues[0])}`);
  checked++;
}

for (const [key, hint] of Object.entries(HINTS)) {
  const examples = hint.split("\n").map((l) => l.trim()).filter((l) => l.startsWith('{"type"'));
  assert.ok(examples.length > 0, `hint "${key}" has no JSON example`);
  for (const ex of examples) {
    const r = LibrarySchema.safeParse(JSON.parse(ex));
    assert.ok(r.success, `hint "${key}" example fails the schema: ${r.success ? "" : JSON.stringify(r.error.issues[0])}`);
    checked++;
  }
}

const types = LIBRARY.map((v) => v.type);
assert.equal(new Set(types).size, types.length, "library types are unique");
for (const t of types) {
  assert.ok(Object.keys(FIXTURES).some((k) => (FIXTURES[k] as any).type === t), `type "${t}" has a fixture`);
  assert.ok((HINTS as Record<string, string>)[t], `type "${t}" has a planner hint`);
}
console.log(`fixtures and hints ok (${checked} specs, ${types.length} visuals)`);
