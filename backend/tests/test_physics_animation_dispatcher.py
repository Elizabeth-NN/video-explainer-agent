import json
from pathlib import Path
import subprocess

import pytest

from app.services import physics_animation_dispatcher as dispatcher


def create_project(tmp_path, *, topic, narrations):
    root = tmp_path

    for animation in dispatcher.ANIMATIONS:
        source = (
            root
            / "backend/app/science/physics"
            / animation["source"]
        )
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("from manim import *\n", encoding="utf-8")

    manifest = root / "backend/generated/narration/manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "topic": topic,
                "scene_count": len(narrations),
                "scenes": [
                    {
                        "scene_number": index,
                        "narration": narration,
                        "audio_file": f"scene_{index:03}.mp3",
                    }
                    for index, narration in enumerate(narrations, start=1)
                ],
            }
        ),
        encoding="utf-8",
    )

    executable = root / "fake-bin/manim"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)

    return root, manifest, executable


def fake_manim_run(calls):
    def run(command, **kwargs):
        calls.append((command, kwargs))
        media_dir = Path(command[command.index("--media_dir") + 1])
        source = Path(command[-2])
        scene_class = command[-1]

        output = (
            media_dir
            / "videos"
            / source.stem
            / "480p15"
            / f"{scene_class}.mp4"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(f"fake-{scene_class}".encode())

        return subprocess.CompletedProcess(command, 0, "", "")

    return run


def test_dispatches_all_five_supported_physics_animations(
    tmp_path, monkeypatch
):
    root, manifest, executable = create_project(
        tmp_path,
        topic="Physics fundamentals",
        narrations=[
            "A projectile follows a parabolic trajectory.",
            "Newton's second law relates net force, mass, and acceleration.",
            "In free fall, an object accelerates under gravity.",
            "Kinematics describes velocity, acceleration, and displacement.",
            "Gravitational potential energy increases with height.",
        ],
    )
    calls = []
    monkeypatch.setattr(
        dispatcher.subprocess,
        "run",
        fake_manim_run(calls),
    )

    result = dispatcher.render_physics_clips(
        manifest_path=manifest,
        output_dir=root / "backend/generated/physics_clips",
        project_root=root,
        manim_executable=executable,
    )

    data = json.loads(manifest.read_text(encoding="utf-8"))

    assert result["status"] == "rendered"
    assert {clip["animation"] for clip in result["clips"]} == {
        "projectile_motion",
        "newtons_second_law",
        "kinematics",
        "free_fall",
        "potential_energy",
    }
    assert len(calls) == 5
    assert all(scene.get("video_file") for scene in data["scenes"])
    assert result["unsupported_scenes"] == []


def test_reuses_one_clip_for_multiple_matching_scenes(tmp_path, monkeypatch):
    root, manifest, executable = create_project(
        tmp_path,
        topic="Newton's second law",
        narrations=[
            "Net force and mass determine acceleration.",
            "The force acting on an object causes acceleration.",
        ],
    )
    calls = []
    monkeypatch.setattr(
        dispatcher.subprocess,
        "run",
        fake_manim_run(calls),
    )

    result = dispatcher.render_physics_clips(
        manifest_path=manifest,
        output_dir=root / "backend/generated/physics_clips",
        project_root=root,
        manim_executable=executable,
    )

    data = json.loads(manifest.read_text(encoding="utf-8"))

    assert result["status"] == "rendered"
    assert len(calls) == 1
    assert len(result["clips"]) == 1
    assert result["clips"][0]["scene_numbers"] == [1, 2]
    assert data["scenes"][0]["video_file"] == data["scenes"][1]["video_file"]


def test_reports_unmatched_scenes_when_other_scenes_are_supported(
    tmp_path, monkeypatch
):
    root, manifest, executable = create_project(
        tmp_path,
        topic="Physics fundamentals",
        narrations=[
            "A projectile follows a parabolic trajectory.",
            "This scene introduces the topic.",
        ],
    )
    monkeypatch.setattr(
        dispatcher.subprocess,
        "run",
        fake_manim_run([]),
    )

    result = dispatcher.render_physics_clips(
        manifest_path=manifest,
        output_dir=root / "backend/generated/physics_clips",
        project_root=root,
        manim_executable=executable,
    )

    data = json.loads(manifest.read_text(encoding="utf-8"))

    assert result["status"] == "rendered"
    assert len(result["unsupported_scenes"]) == 1
    assert result["unsupported_scenes"][0]["scene_number"] == 2
    assert "video_file" in data["scenes"][0]
    assert "video_file" not in data["scenes"][1]


def test_skips_topics_without_supported_physics_animation(
    tmp_path, monkeypatch
):
    root, manifest, executable = create_project(
        tmp_path,
        topic="How the human heart pumps blood",
        narrations=["The heart pumps blood around the body."],
    )
    monkeypatch.setattr(
        dispatcher.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("Manim should not run"),
    )

    result = dispatcher.render_physics_clips(
        manifest_path=manifest,
        output_dir=root / "backend/generated/physics_clips",
        project_root=root,
        manim_executable=executable,
    )

    assert result["status"] == "skipped"
    assert "Supported animations" in result["reason"]
    assert "video_file" not in json.loads(
        manifest.read_text(encoding="utf-8")
    )["scenes"][0]


def test_rejects_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError, match="Narration manifest not found"):
        dispatcher.render_physics_clips(
            manifest_path=tmp_path / "missing.json",
            output_dir=tmp_path / "backend/generated/physics_clips",
            project_root=tmp_path,
        )


def test_rejects_manifest_outside_project(tmp_path):
    root, _, executable = create_project(
        tmp_path,
        topic="Projectile motion",
        narrations=["A projectile follows a parabolic trajectory."],
    )
    outside = tmp_path.parent / "outside-manifest.json"
    outside.write_text(
        json.dumps(
            {
                "topic": "Projectile motion",
                "scenes": [
                    {"scene_number": 1, "narration": "Projectile trajectory."}
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="inside"):
        dispatcher.render_physics_clips(
            manifest_path=outside,
            output_dir=root / "backend/generated/physics_clips",
            project_root=root,
            manim_executable=executable,
        )
