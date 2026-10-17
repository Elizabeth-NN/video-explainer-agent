/**
 * Writes one ExplainerProps JSON file per fixture into remotion/fixtures_out/.
 * Run from the remotion/ directory:
 *   npx tsx src/visuals/make_props.ts
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FIXTURES } from "./fixtures";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = join(__dirname, "../../fixtures_out");
mkdirSync(outDir, { recursive: true });

for (const [name, spec] of Object.entries(FIXTURES)) {
  const props = {
    topic: `Fixture: ${name}`,
    fps: 24,
    width: 1280,
    height: 720,
    scenes: [
      {
        sceneNumber: 1,
        narration: `Fixture visual: ${name}`,
        visualDescription: "",
        audioFile: "silence.wav",
        durationInFrames: 300,
        from: 0,
        visual: spec,
      },
    ],
  };
  const file = join(outDir, `${name}.json`);
  writeFileSync(file, JSON.stringify(props, null, 2), "utf8");
}
console.log(`wrote ${Object.keys(FIXTURES).length} fixture prop files to ${outDir}`);
