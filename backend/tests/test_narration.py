import asyncio
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.narration import generate_narration


def sample_scenes():
    return [
        {
            "scene_number": 1,
            "narration": "Vaccines help the immune system recognize a threat.",
            "visual_description": "Show immune cells recognizing a pathogen.",
            "duration_seconds": 4,
        },
        {
            "scene_number": 2,
            "narration": "The body can then respond more effectively.",
            "visual_description": "Show immune cells responding to a pathogen.",
            "duration_seconds": 3,
        },
    ]


def test_generate_narration_creates_audio_and_manifest(tmp_path: Path):
    async def fake_save(path: str):
        Path(path).write_bytes(b"fake mp3 data")

    class FakeCommunicate:
        def __init__(self, text, voice):
            self.text = text
            self.voice = voice

        async def save(self, path):
            await fake_save(path)

    def fake_run(command, **kwargs):
        if command[0] == "ffprobe":
            stdout = json.dumps({"format": {"duration": "2.5"}})
        else:
            stdout = ""

        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=stdout,
            stderr="",
        )

    with (
        patch("app.services.narration.shutil.which", return_value="/usr/bin/tool"),
        patch("app.services.narration.edge_tts.Communicate", FakeCommunicate),
        patch("app.services.narration.subprocess.run", side_effect=fake_run) as run,
    ):
        result = asyncio.run(
            generate_narration(
                sample_scenes(),
                tmp_path,
                topic="How vaccines work",
            )
        )

    assert result["topic"] == "How vaccines work"
    assert result["scene_count"] == 2
    assert result["voice"] == "en-US-JennyNeural"
    assert result["total_audio_duration_seconds"] == 5.0
    assert result["combined_audio_file"] == "narration.mp3"

    manifest_path = tmp_path / "manifest.json"
    assert manifest_path.exists()

    saved_manifest = json.loads(manifest_path.read_text())
    assert saved_manifest == result
    assert saved_manifest["scenes"][0]["audio_duration_seconds"] == 2.5
    assert saved_manifest["scenes"][0]["audio_file"] == "scene_001.mp3"

    assert (tmp_path / "scene_001.mp3").exists()
    assert (tmp_path / "scene_002.mp3").exists()

    concat_file = tmp_path / "audio_files.txt"
    assert "scene_001.mp3" in concat_file.read_text()
    assert "scene_002.mp3" in concat_file.read_text()

    assert any(
        command.args[0][0] == "ffmpeg"
        for command in run.call_args_list
    )


def test_generate_narration_rejects_empty_scenes(tmp_path: Path):
    with pytest.raises(ValueError, match="without scenes"):
        asyncio.run(generate_narration([], tmp_path))


def test_generate_narration_rejects_empty_scene_text(tmp_path: Path):
    scene = sample_scenes()[0]
    scene["narration"] = "   "

    with (
        patch("app.services.narration.shutil.which", return_value="/usr/bin/tool"),
        pytest.raises(ValueError, match="empty narration"),
    ):
        asyncio.run(generate_narration([scene], tmp_path))


def test_generate_narration_requires_ffmpeg(tmp_path: Path):
    with (
        patch("app.services.narration.shutil.which", return_value=None),
        pytest.raises(RuntimeError, match="ffmpeg is required"),
    ):
        asyncio.run(generate_narration(sample_scenes(), tmp_path))
