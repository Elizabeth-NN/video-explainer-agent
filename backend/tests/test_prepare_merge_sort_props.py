import copy
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prepare_merge_sort_props import (  # noqa: E402
    EXPECTED_PHASES,
    prepare,
    validate_expected_job,
)

NARRATIONS = [
    "Imagine exploring merge sort and discovering how it works.",
    "The key is to understand the evidence behind merge sort.",
    "Start with the main process and the details that explain it.",
    "Merge sort is an efficient, general-purpose, comparison-based sorting algorithm.",
    "Most implementations of merge sort are stable, which means that the relative order of equal elements is the same between the input and output.",
    "Merge sort is a divide-and-conquer algorithm that was invented by John von Neumann in 1945.",
    "A detailed description and analysis of bottom-up merge sort appeared in a report by Goldstine and von Neumann as early as 1948.",
    "In computer science, merge-insertion sort or the Ford–Johnson algorithm is a comparison sorting algorithm published in 1959 by L.",
    "It uses fewer comparisons in the worst case than the best previously known algorithms, binary insertion sort and merge sort, and for 20 years it was the sorting algorithm with the fewest known comparisons.",
    "These details connect the main ideas and show how the process works, while keeping the explanation grounded in the available evidence.",
]


def make_manifest(tmp_path: Path) -> dict:
    audio_files = []
    scenes = []
    for index, narration in enumerate(NARRATIONS, start=1):
        audio_file = f"scene_{index:03d}.mp3"
        (tmp_path / audio_file).write_bytes(b"fake mp3")
        audio_files.append(audio_file)
        scenes.append(
            {
                "scene_number": index,
                "narration": narration,
                "visual_description": f"Describe scene {index}.",
                "visual": {
                    "type": "array",
                    "values": [38, 27, 43, 3, 9, 82, 10],
                    "algorithm": "merge-sort",
                    "footnote": "Illustrative values",
                },
                "audio_duration_seconds": 2.0 + index * 0.01,
                "audio_file": audio_file,
            }
        )
    return {
        "topic": "merge sort",
        "category": "cs",
        "voice": "en-US-JennyNeural",
        "scene_count": len(scenes),
        "total_audio_duration_seconds": 20.55,
        "combined_audio_file": "narration.mp3",
        "scenes": scenes,
    }


def test_prepare_writes_only_new_props_and_preserves_inputs(tmp_path: Path):
    manifest = make_manifest(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    manifest_before = manifest_path.read_bytes()

    input_props = tmp_path / "input-props.json"
    input_props.write_text('{"sentinel": true}\n')
    input_props_before = input_props.read_bytes()

    output = tmp_path / "input-props.merge-sort.phased.json"
    props = prepare(manifest_path, output, input_props)

    assert list(EXPECTED_PHASES.items()) == [
        (1, "overview"),
        (2, "split"),
        (3, "merge"),
        (4, "sorted"),
        (5, "overview"),
        (6, "split"),
        (7, "merge"),
        (9, "sorted"),
        (10, "overview"),
    ]
    assert manifest_path.read_bytes() == manifest_before
    assert input_props.read_bytes() == input_props_before
    assert output.exists()

    saved = json.loads(output.read_text())
    assert saved["fps"] == 24
    assert saved["width"] == 1280
    assert saved["height"] == 720
    assert [scene["visual"]["phase"] for scene in saved["scenes"] if "visual" in scene] == [
        "overview", "split", "merge", "sorted",
        "overview", "split", "merge", "sorted", "overview",
    ]
    assert "visual" not in saved["scenes"][7]

    expected_from = 0
    for source, prepared in zip(manifest["scenes"], saved["scenes"]):
        duration = math.ceil(source["audio_duration_seconds"] * 24)
        assert prepared["sceneNumber"] == source["scene_number"]
        assert prepared["narration"] == source["narration"]
        assert prepared["visualDescription"] == source["visual_description"]
        assert prepared["audioFile"] == f"audio/{source['audio_file']}"
        assert prepared["durationInFrames"] == duration
        assert prepared["from"] == expected_from
        expected_from += duration

    assert props == saved


def test_validate_expected_job_rejects_wrong_phase(tmp_path: Path):
    manifest = make_manifest(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    output = tmp_path / "props.json"
    props = prepare(manifest_path, output, tmp_path / "missing-input-props.json")

    bad = copy.deepcopy(props)
    bad["scenes"][0]["visual"]["phase"] = "split"

    with pytest.raises(ValueError, match="Scene 1 phase"):
        validate_expected_job(bad, tmp_path)
