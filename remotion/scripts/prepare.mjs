import { copyFile, mkdir, readFile, stat, writeFile } from "node:fs/promises";
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

// Allow a specific narration manifest for testing or alternate output directories.
const manifestPath = process.env.REMOTION_MANIFEST_PATH
  ? path.resolve(projectRoot, process.env.REMOTION_MANIFEST_PATH)
  : path.join(backendOutput, "manifest.json");

const narrationOutput = path.dirname(manifestPath);
const manifest = JSON.parse(await readFile(manifestPath, "utf8"));

// The topic and narration must come from the same generation.
if (typeof manifest.topic !== "string" || !manifest.topic.trim()) {
  throw new Error(
    'Narration manifest has no topic. Regenerate narration with "python run_graph.py <topic> --audio" before preparing Remotion.',
  );
}

if (!Array.isArray(manifest.scenes) || manifest.scenes.length === 0) {
  throw new Error("Narration manifest has no scenes.");
}

if (Number(manifest.scene_count) !== manifest.scenes.length) {
  throw new Error(
    `Narration manifest scene_count (${manifest.scene_count}) does not match the ${manifest.scenes.length} scenes present.`,
  );
}

// Keep Remotion independent of potentially stale FFmpeg explainer.json metadata.
const fps = 24;
const width = 1280;
const height = 720;

let startFrame = 0;
const scenes = [];
const videoCopies = [];

for (const [index, scene] of manifest.scenes.entries()) {
  const sceneNumber = Number(scene.scene_number);
  const audioFile = scene.audio_file;
  const durationSeconds = Number(scene.audio_duration_seconds);

  if (!Number.isInteger(sceneNumber) || sceneNumber < 1) {
    throw new Error(`Invalid scene number at manifest index ${index}.`);
  }

  if (
    typeof audioFile !== "string" ||
    !audioFile ||
    path.basename(audioFile) !== audioFile
  ) {
    throw new Error(`Invalid audio filename for scene ${sceneNumber}.`);
  }

  if (
    !Number.isFinite(durationSeconds) ||
    durationSeconds <= 0
  ) {
    throw new Error(`Invalid audio duration for scene ${sceneNumber}.`);
  }

  if (typeof scene.narration !== "string" || !scene.narration.trim()) {
    throw new Error(`Scene ${sceneNumber} has empty narration.`);
  }

  const sourceAudio = path.join(narrationOutput, audioFile);

  // Check that this scene's audio exists before copying it.
  await readFile(sourceAudio);

  // Physics scenes may optionally provide a Manim MP4 path relative
  // to the repository root. CS scenes need no video_file field.
  let videoCopy;
  if (scene.video_file !== undefined) {
    const videoPath = scene.video_file;

    if (
      typeof videoPath !== "string" ||
      !videoPath.trim() ||
      path.isAbsolute(videoPath)
    ) {
      throw new Error(
        `Invalid video_file for scene ${sceneNumber}: expected a relative project path.`,
      );
    }

    const sourceVideo = path.resolve(projectRoot, videoPath);
    const relativeVideo = path.relative(projectRoot, sourceVideo);

    if (
      relativeVideo === ".." ||
      relativeVideo.startsWith(`..${path.sep}`) ||
      path.isAbsolute(relativeVideo)
    ) {
      throw new Error(
        `Video path for scene ${sceneNumber} must stay inside the project.`,
      );
    }

    if (path.extname(sourceVideo).toLowerCase() !== ".mp4") {
      throw new Error(
        `Video for scene ${sceneNumber} must be an MP4 file.`,
      );
    }

    // Check the file without loading the entire video into memory.
    let videoInfo;
    try {
      videoInfo = await stat(sourceVideo);
    } catch {
      throw new Error(
        `Video for scene ${sceneNumber} does not exist or cannot be accessed: ${videoPath}`,
      );
    }

    if (!videoInfo.isFile()) {
      throw new Error(
        `Video for scene ${sceneNumber} must point to a file: ${videoPath}`,
      );
    }

    videoCopy = {
      source: sourceVideo,
      publicFile: `videos/scene_${String(sceneNumber).padStart(3, "0")}.mp4`,
    };
    videoCopies.push(videoCopy);
  }

  const durationInFrames = Math.ceil(durationSeconds * fps);

  scenes.push({
    sceneNumber,
    narration: scene.narration,
    visualDescription: String(scene.visual_description || ""),
    ...(scene.visual && typeof scene.visual === "object"
      ? { visual: scene.visual }
      : {}),
    audioFile: `audio/${audioFile}`,
    ...(videoCopy ? { videoFile: videoCopy.publicFile } : {}),
    durationInFrames,
    from: startFrame,
  });

  startFrame += durationInFrames;
}

const publicAudio = path.join(here, "../public/audio");
await mkdir(publicAudio, { recursive: true });

for (const scene of manifest.scenes) {
  const audioFile = scene.audio_file;
  await copyFile(
    path.join(narrationOutput, audioFile),
    path.join(publicAudio, audioFile),
  );
}

if (videoCopies.length > 0) {
  const publicVideos = path.join(here, "../public/videos");
  await mkdir(publicVideos, { recursive: true });

  for (const video of videoCopies) {
    await copyFile(
      video.source,
      path.join(publicVideos, path.basename(video.publicFile)),
    );
  }
}

const props = {
  topic: manifest.topic.trim(),
  fps,
  width,
  height,
  scenes,
};

await writeFile(
  path.join(here, "../input-props.json"),
  JSON.stringify(props, null, 2) + "\n",
);

console.log(`Prepared ${scenes.length} scenes for "${props.topic}".`);
console.log(`Duration: ${(startFrame / fps).toFixed(2)} seconds.`);
console.log(`Frame rate: ${fps} fps.`);
console.log(`Resolution: ${width}x${height}.`);
