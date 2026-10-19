import json
from pathlib import Path
import subprocess

import pytest

from app.services import physics_video_renderer as renderer


def create_project(tmp_path, *, topic="Projectile motion", narration=None):
    root = tmp_path
    source = root / "backend/app/science/physics/projectile_motion.py"
    source.parent.mkdir(parents=True)
    source.write_text("from manim import *\n", encoding="utf-8")

    manifest = root / "backend/generated/narration/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "topic": topic,
                "scene_count": 1,
                "scenes": [
                    {
                        "scene_number": 1,
                        "narration": narration or (
                            "The projectile follows a parabolic trajectory."
                        ),
                        "audio_file": "scene_001.mp3",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    executable = root / "fake-bin/manim"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")

    return root, manifest, executable


def test_renders_clip_and_attaches_it_to_matching_scene(tmp_path, monkeypatch):
    root, manifest, executable = create_project(tmp_path)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        media_dir = Path(command[command.index("--media_dir") + 1])
        output = (
            media_dir
            / "videos/projectile_motion/480p15/ProjectileMotion.mp4"
        )
        output.parent.mkdir(parents=True)
        output.write_bytes(b"test-video")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(renderer.subprocess, "run", fake_run)

    result = renderer.render_projectile_motion_clip(
        manifest_path=manifest,
        output_dir=root / "backend/generated/narration/physics_clips",
        project_root=root,
        manim_executable=executable,
    )

    data = json.loads(manifest.read_text())
    scene = data["scenes"][0]

    assert result["status"] == "rendered"
    assert result["scene_number"] == 1
    assert scene["video_file"] == (
        "backend/generated/narration/physics_clips/projectile_motion.mp4"
    )
    assert (root / scene["video_file"]).read_bytes() == b"test-video"
    assert len(calls) == 1
    assert "-ql" in calls[0][0]
    assert calls[0][1]["check"] is True


def test_skips_non_projectile_topic(tmp_path, monkeypatch):
    root, manifest, executable = create_project(
        tmp_path,
        topic="How the human heart pumps blood",
    )
    monkeypatch.setattr(
        renderer.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("Manim should not run"),
    )

    result = renderer.render_projectile_motion_clip(
        manifest_path=manifest,
        output_dir=root / "backend/generated/narration/physics_clips",
        project_root=root,
        manim_executable=executable,
    )

    assert result["status"] == "skipped"
    assert "not supported" in result["reason"]
    assert "video_file" not in json.loads(manifest.read_text())["scenes"][0]


def test_skips_when_no_scene_matches_projectile_motion(tmp_path, monkeypatch):
    root, manifest, executable = create_project(
        tmp_path,
        narration="This scene introduces the topic.",
    )
    monkeypatch.setattr(
        renderer.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("Manim should not run"),
    )

    result = renderer.render_projectile_motion_clip(
        manifest_path=manifest,
        output_dir=root / "backend/generated/narration/physics_clips",
        project_root=root,
        manim_executable=executable,
    )

    assert result["status"] == "skipped"
    assert "No narration scene" in result["reason"]


def test_rejects_manifest_outside_project(tmp_path):
    root, _, executable = create_project(tmp_path)
    outside = tmp_path.parent / "outside-manifest.json"
    outside.write_text(
        json.dumps({"topic": "Projectile motion", "scenes": []}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="inside"):
        renderer.render_projectile_motion_clip(
            manifest_path=outside,
            output_dir=root / "backend/generated/narration/physics_clips",
            project_root=root,
            manim_executable=executable,
        )


def test_reports_manim_failure(tmp_path, monkeypatch):
    root, manifest, executable = create_project(tmp_path)

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(
            1,
            args[0],
            stdout="",
            stderr="Simulated Manim failure",
        )

    monkeypatch.setattr(renderer.subprocess, "run", fail)

    with pytest.raises(RuntimeError, match="Simulated Manim failure"):
        renderer.render_projectile_motion_clip(
            manifest_path=manifest,
            output_dir=root / "backend/generated/narration/physics_clips",
            project_root=root,
            manim_executable=executable,
        )


def test_rejects_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError, match="Narration manifest not found"):
        renderer.render_projectile_motion_clip(
            manifest_path=tmp_path / "missing.json",
            output_dir=tmp_path / "backend/generated/narration/physics_clips",
            project_root=tmp_path,
        )
