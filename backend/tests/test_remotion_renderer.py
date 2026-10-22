import json
from pathlib import Path
import subprocess

import pytest

from app.services import remotion_renderer


def make_manifest(path: Path, scenes=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "topic": "Test topic",
                "scene_count": len(scenes if scenes is not None else [{"scene_number": 1}]),
                "scenes": scenes if scenes is not None else [{"scene_number": 1}],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_render_remotion_video_prepares_renders_and_writes_metadata(
    tmp_path, monkeypatch
):
    root = tmp_path
    remotion_dir = root / "remotion"
    remotion_dir.mkdir()

    manifest = make_manifest(root / "backend/generated/narration/manifest.json")
    output = root / "backend/generated/narration/explainer.mp4"
    calls = []

    def fake_run(command, *, cwd, env, timeout, stage):
        calls.append(
            {
                "command": command,
                "cwd": cwd,
                "env": env,
                "timeout": timeout,
                "stage": stage,
            }
        )

        if stage == "video rendering":
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"fake-mp4")

        if stage == "metadata inspection":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=json.dumps(
                    {
                        "format": {"duration": "9.083"},
                        "streams": [
                            {
                                "codec_type": "video",
                                "width": 1280,
                                "height": 720,
                                "r_frame_rate": "24/1",
                            },
                            {"codec_type": "audio"},
                        ],
                    }
                ),
                stderr="",
            )

        return subprocess.CompletedProcess(
            command, 0, stdout="", stderr=""
        )

    monkeypatch.setattr(remotion_renderer, "_run_command", fake_run)
    monkeypatch.setattr(remotion_renderer.shutil, "which", lambda name: "/usr/bin/ffprobe")

    result = remotion_renderer.render_remotion_video(
        manifest_path=manifest,
        output_path=output,
        project_root=root,
    )

    assert [call["stage"] for call in calls] == [
        "preparation",
        "video rendering",
        "metadata inspection",
    ]
    assert calls[0]["command"] == ["node", "scripts/prepare.mjs"]
    assert calls[0]["env"]["REMOTION_MANIFEST_PATH"] == (
        "backend/generated/narration/manifest.json"
    )
    assert "--concurrency=1" in calls[1]["command"]
    assert result["renderer"] == "remotion"
    assert result["output_file"] == str(output)
    assert result["width"] == 1280
    assert result["height"] == 720
    assert result["fps"] == 24
    assert result["duration_seconds"] == 9.083
    assert result["scene_count"] == 1

    metadata_path = output.with_suffix(".json")
    assert metadata_path.is_file()
    assert json.loads(metadata_path.read_text()) == result


def test_render_remotion_video_rejects_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError, match="Narration manifest not found"):
        remotion_renderer.render_remotion_video(
            manifest_path=tmp_path / "missing.json",
            output_path=tmp_path / "out.mp4",
            project_root=tmp_path,
        )


def test_render_remotion_video_rejects_empty_scene_list(tmp_path):
    root = tmp_path
    (root / "remotion").mkdir()
    manifest = make_manifest(
        root / "backend/generated/narration/manifest.json",
        scenes=[],
    )

    with pytest.raises(ValueError, match="at least one scene"):
        remotion_renderer.render_remotion_video(
            manifest_path=manifest,
            output_path=root / "out.mp4",
            project_root=root,
        )


def test_render_remotion_video_rejects_manifest_outside_project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "remotion").mkdir()
    outside_manifest = make_manifest(tmp_path / "outside/manifest.json")

    with pytest.raises(ValueError, match="must be inside"):
        remotion_renderer.render_remotion_video(
            manifest_path=outside_manifest,
            output_path=root / "out.mp4",
            project_root=root,
        )


def test_render_remotion_video_rejects_zero_concurrency(tmp_path):
    root = tmp_path
    (root / "remotion").mkdir()
    manifest = make_manifest(root / "backend/generated/narration/manifest.json")

    with pytest.raises(ValueError, match="concurrency must be at least 1"):
        remotion_renderer.render_remotion_video(
            manifest_path=manifest,
            output_path=root / "out.mp4",
            project_root=root,
            concurrency=0,
        )


def test_render_remotion_video_reports_subprocess_failure(tmp_path, monkeypatch):
    root = tmp_path
    (root / "remotion").mkdir()
    manifest = make_manifest(root / "backend/generated/narration/manifest.json")

    def fail_subprocess(*args, **kwargs):
        raise subprocess.CalledProcessError(
            1,
            args[0] if args else kwargs.get("args", ["node"]),
            output="",
            stderr="Simulated Remotion failure",
        )

    # Mock subprocess.run, not _run_command, so the real error handler runs.
    monkeypatch.setattr(remotion_renderer.subprocess, "run", fail_subprocess)

    with pytest.raises(RuntimeError, match="Simulated Remotion failure"):
        remotion_renderer.render_remotion_video(
            manifest_path=manifest,
            output_path=root / "out.mp4",
            project_root=root,
        )
