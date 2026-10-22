import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prepare_binary_search_props import (  # noqa: E402
    _skipped_competing_scenes,
    build_binary_search_props,
    prepare,
    validate_binary_search_job,
)

NARRATIONS = [
    "Imagine searching a sorted list for one target value.",
    "Binary search compares the target value to the middle element.",
    "The target is found and the search is finished.",
    "Bubble sort compares adjacent values.",
    "These details summarize the process.",
]


def make_manifest(tmp_path: Path) -> dict:
    scenes = []
    for index, narration in enumerate(NARRATIONS, start=1):
        audio_file = f"scene_{index:03d}.mp3"
        (tmp_path / audio_file).write_bytes(b"fake mp3")
        scene = {
            "scene_number": index,
            "narration": narration,
            "visual_description": f"Describe scene {index}.",
            "audio_duration_seconds": 2.0 + index * 0.01,
            "audio_file": audio_file,
        }
        if index == 2:
            scene["visual"] = {
                "type": "array",
                "values": [3, 8, 12, 19, 25, 31, 42],
                "algorithm": "binary-search",
                "target": 25,
            }
        elif index == 3:
            scene["visual"] = {
                "type": "array",
                "values": [3, 8, 12, 19, 25, 31, 42],
                "algorithm": "binary-search",
                "target": 8,
                "phase": "found",
            }
        elif index == 4:
            scene["visual"] = {
                "type": "array",
                "values": [5, 2, 9],
                "algorithm": "bubble-sort",
            }
        scenes.append(scene)
    return {
        "topic": "How binary search works",
        "category": "cs",
        "voice": "en-US-JennyNeural",
        "scene_count": len(scenes),
        "total_audio_duration_seconds": 10.15,
        "combined_audio_file": "narration.mp3",
        "scenes": scenes,
    }


def test_binary_search_props_assign_and_preserve(tmp_path: Path):
    manifest = make_manifest(tmp_path)
    props = build_binary_search_props(manifest, tmp_path)

    assert len(props["scenes"]) == len(manifest["scenes"])
    assert [scene["sceneNumber"] for scene in props["scenes"]] == [1, 2, 3, 4, 5]
    assert props["scenes"][1]["visual"]["phase"] == "midpoint"
    assert props["scenes"][2]["visual"]["phase"] == "found"
    assert props["scenes"][1]["visual"]["target"] == 25
    assert props["scenes"][2]["visual"]["target"] == 8
    assert props["scenes"][0]["visual"]["algorithm"] == "binary-search"
    assert props["scenes"][4]["visual"]["algorithm"] == "binary-search"
    # A scene explicitly discussing Bubble Sort must remain untouched.
    assert props["scenes"][3]["visual"]["algorithm"] == "bubble-sort"

    validate_binary_search_job(props, manifest, tmp_path)

    expected_from = 0
    for source, prepared in zip(manifest["scenes"], props["scenes"]):
        duration = math.ceil(source["audio_duration_seconds"] * 24)
        assert prepared["audioFile"] == f"audio/{source['audio_file']}"
        assert prepared["durationInFrames"] == duration
        assert prepared["from"] == expected_from
        expected_from += duration


def test_prepare_writes_only_output_and_preserves_inputs(tmp_path: Path):
    manifest = make_manifest(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    manifest_before = manifest_path.read_bytes()

    input_props = tmp_path / "input-props.json"
    input_props.write_text('{"sentinel": true}\n')
    input_props_before = input_props.read_bytes()
    output = tmp_path / "input-props.binary-search.phased.json"

    props, skipped = prepare(manifest_path, output, input_props)

    assert skipped == []
    assert output.exists()
    assert json.loads(output.read_text()) == props
    assert manifest_path.read_bytes() == manifest_before
    assert input_props.read_bytes() == input_props_before


def test_competing_algorithm_is_reported_as_skipped(tmp_path: Path):
    manifest = make_manifest(tmp_path)
    manifest["scenes"][1]["narration"] = "Insertion sort builds a sorted prefix."

    skipped = _skipped_competing_scenes(manifest)

    assert skipped == [
        (2, "Insertion sort builds a sorted prefix."),
    ]


def test_conflicting_visual_is_repaired_without_mutating_manifest(
    tmp_path: Path,
):
    manifest = make_manifest(tmp_path)
    scene = manifest["scenes"][4]
    scene["visual"] = {
        "type": "array",
        "values": [5, 2, 9],
        "algorithm": "bubble-sort",
    }
    original_visual = json.loads(json.dumps(scene["visual"]))

    props = build_binary_search_props(manifest, tmp_path)

    assert props["scenes"][4]["visual"]["algorithm"] == "binary-search"
    assert scene["visual"] == original_visual


def test_competing_algorithm_scene_is_preserved(tmp_path: Path):
    manifest = make_manifest(tmp_path)
    original_visual = json.loads(json.dumps(manifest["scenes"][3]["visual"]))

    props = build_binary_search_props(manifest, tmp_path)

    assert props["scenes"][3]["visual"] == original_visual


def test_no_eligible_binary_search_visuals_is_rejected(tmp_path: Path):
    manifest = make_manifest(tmp_path)
    for scene in manifest["scenes"]:
        scene.pop("visual", None)
        scene["narration"] = "Bubble sort compares adjacent values."

    props = build_binary_search_props(manifest, tmp_path)
    with pytest.raises(ValueError, match="no usable Binary Search"):
        validate_binary_search_job(props, manifest, tmp_path)
