"""One-off, non-destructive Merge Sort props preparation.

Reads an existing web-job manifest, applies the planner's Merge Sort phase
assignment to a deep copy of its scenes, and writes Remotion props to a new
file. It never rewrites the source manifest, remotion/input-props.json, audio,
or video.

Run from the repository root:

    python backend/prepare_merge_sort_props.py
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.graph.scene_planner import _MERGE_SORT_PHASES, _assign_merge_sort_phases

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "backend"
    / "generated"
    / "web_jobs"
    / "1983274c-51df-4c36-a204-8e04b41ad373"
    / "manifest.json"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "remotion" / "input-props.merge-sort.phased.json"
DEFAULT_INPUT_PROPS = PROJECT_ROOT / "remotion" / "input-props.json"

FPS = 24
WIDTH = 1280
HEIGHT = 720

EXPECTED_PHASES = {
    1: "overview",
    2: "split",
    3: "merge",
    4: "sorted",
    5: "overview",
    6: "split",
    7: "merge",
    9: "sorted",
    10: "overview",
}


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if not isinstance(manifest.get("topic"), str) or not manifest["topic"].strip():
        raise ValueError("Manifest has no topic.")
    scenes = manifest.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Manifest has no scenes.")
    if manifest.get("scene_count") != len(scenes):
        raise ValueError(
            f"scene_count={manifest.get('scene_count')!r} does not match "
            f"{len(scenes)} scenes."
        )

    for index, scene in enumerate(scenes):
        number = scene.get("scene_number")
        if not isinstance(number, int) or number < 1:
            raise ValueError(f"Invalid scene_number at index {index}: {number!r}")
        if not isinstance(scene.get("narration"), str) or not scene["narration"].strip():
            raise ValueError(f"Scene {number} has empty narration.")
        duration = scene.get("audio_duration_seconds")
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
            raise ValueError(f"Scene {number} has invalid audio_duration_seconds.")
        audio_file = scene.get("audio_file")
        if (
            not isinstance(audio_file, str)
            or not audio_file
            or Path(audio_file).name != audio_file
        ):
            raise ValueError(f"Scene {number} has an invalid audio_file.")
        if "video_file" in scene:
            raise ValueError(
                f"Scene {number} uses video_file; this one-off utility does not "
                "prepare video copies."
            )


def build_remotion_props(
    manifest: dict[str, Any],
    manifest_dir: Path,
    phase_assigner: Callable[[list[dict]], None] | None = None,
) -> dict[str, Any]:
    """Convert a job manifest to Remotion props without touching source files."""
    _validate_manifest(manifest)
    scenes = copy.deepcopy(manifest["scenes"])
    if phase_assigner is not None:
        phase_assigner(scenes)

    props_scenes: list[dict[str, Any]] = []
    start_frame = 0
    for scene in scenes:
        number = scene["scene_number"]
        duration_seconds = float(scene["audio_duration_seconds"])
        audio_file = scene["audio_file"]
        source_audio = manifest_dir / audio_file

        if not source_audio.is_file():
            raise FileNotFoundError(f"Scene {number} audio not found: {source_audio}")

        duration_in_frames = math.ceil(duration_seconds * FPS)
        props_scene: dict[str, Any] = {
            "sceneNumber": number,
            "narration": scene["narration"],
            "visualDescription": str(scene.get("visual_description") or ""),
        }
        if isinstance(scene.get("visual"), dict):
            props_scene["visual"] = scene["visual"]
        props_scene["audioFile"] = f"audio/{audio_file}"
        props_scene["durationInFrames"] = duration_in_frames
        props_scene["from"] = start_frame
        props_scenes.append(props_scene)
        start_frame += duration_in_frames

    props: dict[str, Any] = {
        "topic": manifest["topic"].strip(),
        "category": (
            manifest["category"]
            if manifest.get("category") in {"cs", "physics"}
            else None
        ),
        "fps": FPS,
        "width": WIDTH,
        "height": HEIGHT,
        "scenes": props_scenes,
    }
    if props["category"] is None:
        props.pop("category")
    return props


def _build_props(manifest: dict[str, Any], manifest_dir: Path) -> dict[str, Any]:
    return build_remotion_props(
        manifest, manifest_dir, _assign_merge_sort_phases
    )

def validate_expected_job(props: dict[str, Any], manifest_dir: Path) -> None:
    """Validate the concrete 10-scene Merge Sort job and required fields."""
    scenes = props.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != 10:
        raise ValueError(f"Expected 10 props scenes, got {len(scenes or [])}.")

    if props.get("fps") != FPS or props.get("width") != WIDTH or props.get("height") != HEIGHT:
        raise ValueError("Props dimensions or frame rate do not match prepare.mjs.")

    expected_from = 0
    for scene in scenes:
        number = scene["sceneNumber"]
        if scene["from"] != expected_from:
            raise ValueError(f"Scene {number} from={scene['from']} != {expected_from}.")
        expected_from += scene["durationInFrames"]
        if scene["durationInFrames"] < 1:
            raise ValueError(f"Scene {number} has no frames.")
        if not scene["narration"].strip():
            raise ValueError(f"Scene {number} has no narration.")
        if not scene["audioFile"].startswith("audio/"):
            raise ValueError(f"Scene {number} has an invalid audioFile.")
        source_audio = manifest_dir / scene["audioFile"].removeprefix("audio/")
        if not source_audio.is_file():
            raise ValueError(f"Scene {number} source audio missing: {source_audio}")

        visual = scene.get("visual")
        if number == 8:
            if visual is not None:
                raise ValueError("Scene 8 must not have a visual.")
            continue

        expected_phase = EXPECTED_PHASES.get(number)
        if expected_phase is None:
            raise ValueError(f"Unexpected scene number {number}.")
        if not isinstance(visual, dict):
            raise ValueError(f"Scene {number} is missing its Merge Sort visual.")
        if visual.get("algorithm") != "merge-sort" or visual.get("type") != "array":
            raise ValueError(f"Scene {number} is not a Merge Sort array visual.")
        if visual.get("phase") != expected_phase:
            raise ValueError(
                f"Scene {number} phase={visual.get('phase')!r}, expected {expected_phase!r}."
            )
        if visual.get("phase") not in _MERGE_SORT_PHASES:
            raise ValueError(f"Scene {number} has an invalid Merge Sort phase.")

    merge_count = sum(
        1
        for scene in scenes
        if isinstance(scene.get("visual"), dict)
        and scene["visual"].get("algorithm") == "merge-sort"
    )
    if merge_count != 9:
        raise ValueError(f"Expected 9 Merge Sort scenes, got {merge_count}.")


def prepare(
    manifest_path: Path = DEFAULT_MANIFEST,
    output_path: Path = DEFAULT_OUTPUT,
    input_props_path: Path = DEFAULT_INPUT_PROPS,
) -> dict[str, Any]:
    manifest_path = manifest_path.resolve()
    output_path = output_path.resolve()
    input_props_path = input_props_path.resolve()

    if output_path in {manifest_path, input_props_path}:
        raise ValueError("Output must not be the source manifest or input-props.json.")
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    manifest_hash = _sha256(manifest_path)
    input_props_hash = _sha256(input_props_path)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    props = _build_props(manifest, manifest_path.parent)
    validate_expected_job(props, manifest_path.parent)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(props, indent=2) + "\n", encoding="utf-8")

    if _sha256(manifest_path) != manifest_hash:
        raise RuntimeError("Source manifest changed during preparation.")
    if _sha256(input_props_path) != input_props_hash:
        raise RuntimeError("remotion/input-props.json changed during preparation.")

    return props


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    props = prepare(args.manifest, args.output)
    phases = [
        (scene["sceneNumber"], scene.get("visual", {}).get("phase"))
        for scene in props["scenes"]
    ]
    print(f"Wrote {args.output}")
    for number, phase in phases:
        print(f"scene {number:>2}: {phase or '<no visual>'}")


if __name__ == "__main__":
    main()
