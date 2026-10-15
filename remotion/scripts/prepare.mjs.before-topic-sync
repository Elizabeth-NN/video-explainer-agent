import { copyFile, mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(here, "../..");
const backendOutput = path.join(
  projectRoot,
  "backend",
  "generated",
  "narration",
);

const manifest = JSON.parse(
  await readFile(path.join(backendOutput, "manifest.json"), "utf8"),
);
const video = JSON.parse(
  await readFile(path.join(backendOutput, "explainer.json"), "utf8"),
);

const publicAudio = path.join(here, "../public/audio");
await mkdir(publicAudio, { recursive: true });

const fps = Number(video.fps || 24);
let startFrame = 0;

const scenes = [];

for (const scene of manifest.scenes) {
  const audioFile = scene.audio_file;
  const sourceAudio = path.join(backendOutput, audioFile);
  await copyFile(sourceAudio, path.join(publicAudio, audioFile));

  const durationInFrames = Math.ceil(
    Number(scene.audio_duration_seconds) * fps,
  );

  scenes.push({
    sceneNumber: Number(scene.scene_number),
    narration: String(scene.narration),
    visualDescription: String(scene.visual_description || ""),
    audioFile: `audio/${audioFile}`,
    durationInFrames,
    from: startFrame,
  });

  startFrame += durationInFrames;
}

const props = {
  topic: String(video.topic || "An explainer"),
  fps,
  width: Number(video.width || 1280),
  height: Number(video.height || 720),
  scenes,
};

await writeFile(
  path.join(here, "../input-props.json"),
  JSON.stringify(props, null, 2) + "\n",
);

console.log(`Prepared ${scenes.length} scenes for "${props.topic}".`);
console.log(`Duration: ${(startFrame / fps).toFixed(2)} seconds.`);
console.log(`Frame rate: ${fps} fps.`);
