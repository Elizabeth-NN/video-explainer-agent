"""One-off, non-destructive Binary Search props preparation.

Reads an existing Binary Search job manifest, applies only the planner's
Binary Search phase assignment to a deep copy of its scenes, and writes Remotion
props to a new file. It never rewrites the source manifest, audio, or
remotion/input-props.json.

Run from the repository root:

    python backend/prepare_binary_search_props.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.graph.scene_planner import (
    _BINARY_SEARCH_PHASES,
    _assign_binary_search_phases,
    _named_algorithms,
)
from prepare_merge_sort_props import (
    DEFAULT_INPUT_PROPS,
    FPS,
    HEIGHT,
    WIDTH,
    _sha256,
    build_remotion_props,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    PROJECT_ROOT
    / "backend"
    / "generated"
    / "cs-binary-search-final-check"
    / "manifest.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT / "remotion" / "input-props.binary-search.phased.json"
)


def _binary_visual(scene: dict[str, Any]) -> dict[str, Any] | None:
    visual = scene.get("visual")
    if (
        isinstance(visual, dict)
        and visual.get("type") == "array"
        and visual.get("algorithm") == "binary-search"
    ):
        return visual
    return None


def _skipped_competing_scenes(manifest: dict[str, Any]) -> list[tuple[int, str]]:
    skipped: list[tuple[int, str]] = []
    for scene in manifest["scenes"]:
        visual = _binary_visual(scene)
        if visual is None or visual.get("phase") in _BINARY_SEARCH_PHASES:
            continue
        algorithms = _named_algorithms(str(scene.get("narration", "")))
        if algorithms - {"binary-search"} and "binary-search" not in algorithms:
            skipped.append((scene["scene_number"], scene["narration"]))
    return skipped


def build_binary_search_props(
    manifest: dict[str, Any], manifest_dir: Path
) -> dict[str, Any]:
    return build_remotion_props(
        manifest, manifest_dir, _assign_binary_search_phases
    )


def validate_binary_search_job(
    props: dict[str, Any],
    source_manifest: dict[str, Any],
    manifest_dir: Path,
) -> None:
    """Validate the concrete job without adding or removing scenes."""
    scenes = props.get("scenes")
    source_scenes = source_manifest.get("scenes")
    if not isinstance(scenes, list) or not isinstance(source_scenes, list):
        raise ValueError("Props or source manifest has no scenes.")
    if len(scenes) != len(source_scenes):
        raise ValueError(
            f"Scene loss: props has {len(scenes)}, manifest has {len(source_scenes)}."
        )
    if [s["sceneNumber"] for s in scenes] != [
        s["scene_number"] for s in source_scenes
    ]:
        raise ValueError("Prepared scene order/numbers do not match the manifest.")

    if props.get("fps") != FPS or props.get("width") != WIDTH or props.get("height") != HEIGHT:
        raise ValueError("Props dimensions or frame rate do not match prepare.mjs.")

    original_by_number = {
        scene["scene_number"]: scene for scene in source_scenes
    }
    expected_from = 0
    binary_count = 0

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
        if not (manifest_dir / scene["audioFile"].removeprefix("audio/")).is_file():
            raise ValueError(f"Scene {number} source audio is missing.")

        visual = _binary_visual(scene)
        if visual is None:
            continue
        binary_count += 1
        phase = visual.get("phase")
        if phase not in _BINARY_SEARCH_PHASES:
            raise ValueError(
                f"Scene {number} Binary Search phase is missing or invalid: {phase!r}"
            )

        source_visual = original_by_number[number].get("visual") or {}
        if (
            source_visual.get("phase") in _BINARY_SEARCH_PHASES
            and source_visual.get("phase") != phase
        ):
            raise ValueError(f"Scene {number} changed an explicit phase.")
        if (
            "target" in source_visual
            and visual.get("target") != source_visual.get("target")
        ):
            raise ValueError(f"Scene {number} changed its existing target.")

    if binary_count == 0:
        raise ValueError("Manifest contains no usable Binary Search array visuals.")


def prepare(
    manifest_path: Path = DEFAULT_MANIFEST,
    output_path: Path = DEFAULT_OUTPUT,
    input_props_path: Path = DEFAULT_INPUT_PROPS,
) -> tuple[dict[str, Any], list[tuple[int, str]]]:
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
    skipped = _skipped_competing_scenes(manifest)
    props = build_binary_search_props(manifest, manifest_path.parent)
    validate_binary_search_job(props, manifest, manifest_path.parent)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(props, indent=2) + "\n", encoding="utf-8")

    if _sha256(manifest_path) != manifest_hash:
        raise RuntimeError("Source manifest changed during preparation.")
    if _sha256(input_props_path) != input_props_hash:
        raise RuntimeError("remotion/input-props.json changed during preparation.")

    return props, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    props, skipped = prepare(args.manifest, args.output)
    print(f"Wrote {args.output}")
    for scene in props["scenes"]:
        visual = scene.get("visual")
        if isinstance(visual, dict):
            label = f"{visual.get('algorithm')}/{visual.get('phase')}"
        else:
            label = "<no visual>"
        print(f"scene {scene['sceneNumber']:>2}: {label}")

    if skipped:
        print("Skipped because narration names another algorithm:")
        for number, narration in skipped:
            print(f"  scene {number}: {narration}")
    else:
        print("Skipped because narration names another algorithm: none")


if __name__ == "__main__":
    main()
