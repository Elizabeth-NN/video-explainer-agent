import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.video_renderer import render_video


def sample_scenes():
    return [
        {
            "scene_number": 1,
            "narration": "Vaccines help the immune system recognize a threat.",
            "visual_description": "Illustrate immune cells recognizing a pathogen.",
            "duration_seconds": 4,
        },
        {
            "scene_number": 2,
            "narration": "The body can then respond more effectively.",
            "visual_description": "Illustrate an immune response.",
            "duration_seconds": 3,
        },
    ]


def create_narration_manifest(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)

    scenes = []
    for number, duration in [(1, 2.5), (2, 2.5)]:
        filename = f"scene_{number:03d}.mp3"
        (directory / filename).write_bytes(b"fake audio")

        scenes.append(
            {
                "scene_number": number,
                "narration": sample_scenes()[number - 1]["narration"],
                "visual_description": sample_scenes()[number - 1][
                    "visual_description"
                ],
                "estimated_duration_seconds": 4,
                "audio_duration_seconds": duration,
                "audio_file": filename,
            }
        )

    manifest = {
        "voice": "en-US-AriaNeural",
        "scene_count": len(scenes),
        "total_audio_duration_seconds": 5.0,
        "combined_audio_file": "narration.mp3",
        "scenes": scenes,
    }

    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_render_video_creates_mp4_and_metadata(tmp_path: Path):
    narration_manifest = create_narration_manifest(tmp_path)
    output_path = tmp_path / "explainer.mp4"
    ffmpeg_commands = []

    def fake_run(command, cwd):
        if command[0] == "ffmpeg":
            ffmpeg_commands.append(command)
            output_file = Path(command[-1])

            if not output_file.is_absolute():
                output_file = cwd / output_file

            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_bytes(b"fake video data")
            return ""

        if command[0] == "ffprobe":
            return json.dumps(
                {
                    "format": {
                        "duration": "5.0",
                        "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                    }
                }
            )

        raise AssertionError(f"Unexpected command: {command}")

    with (
        patch(
            "app.services.video_renderer.shutil.which",
            return_value="/usr/bin/tool",
        ),
        patch(
            "app.services.video_renderer._run",
            side_effect=fake_run,
        ),
    ):
        result = render_video(
            scenes=sample_scenes(),
            narration_manifest_path=narration_manifest,
            output_path=output_path,
            topic="How vaccines work",
        )

    assert output_path.exists()
    assert result["topic"] == "How vaccines work"
    assert result["scene_count"] == 2
    assert result["width"] == 1280
    assert result["height"] == 720
    assert result["fps"] == 24
    assert result["duration_seconds"] == 5.0
    assert result["format"].startswith("mov")

    metadata_path = tmp_path / "explainer.json"
    assert metadata_path.exists()

    saved_result = json.loads(metadata_path.read_text())
    assert saved_result == result

    # Two scene videos and one final concatenation.
    assert len(ffmpeg_commands) == 3

    for command in ffmpeg_commands[:2]:
        assert "drawtext" in command[command.index("-vf") + 1]
        assert "libx264" in command
        assert "aac" in command

    assert any("concat" in command for command in ffmpeg_commands)


def test_render_video_rejects_empty_scenes(tmp_path: Path):
    with pytest.raises(ValueError, match="without scenes"):
        render_video(
            scenes=[],
            narration_manifest_path=tmp_path / "manifest.json",
            output_path=tmp_path / "explainer.mp4",
        )


def test_render_video_requires_ffmpeg(tmp_path: Path):
    manifest_path = create_narration_manifest(tmp_path)

    with (
        patch("app.services.video_renderer.shutil.which", return_value=None),
        pytest.raises(RuntimeError, match="ffmpeg is required"),
    ):
        render_video(
            scenes=sample_scenes(),
            narration_manifest_path=manifest_path,
            output_path=tmp_path / "explainer.mp4",
        )


def test_render_video_rejects_missing_manifest(tmp_path: Path):
    with (
        patch(
            "app.services.video_renderer.shutil.which",
            return_value="/usr/bin/tool",
        ),
        pytest.raises(FileNotFoundError, match="Narration manifest not found"),
    ):
        render_video(
            scenes=sample_scenes(),
            narration_manifest_path=tmp_path / "missing.json",
            output_path=tmp_path / "explainer.mp4",
        )


def test_render_video_rejects_missing_scene_audio(tmp_path: Path):
    manifest_path = create_narration_manifest(tmp_path)
    (tmp_path / "scene_002.mp3").unlink()

    with (
        patch(
            "app.services.video_renderer.shutil.which",
            return_value="/usr/bin/tool",
        ),
        pytest.raises(FileNotFoundError, match="Audio for scene 2 not found"),
    ):
        render_video(
            scenes=sample_scenes(),
            narration_manifest_path=manifest_path,
            output_path=tmp_path / "explainer.mp4",
        )
