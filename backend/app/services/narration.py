import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import edge_tts


DEFAULT_VOICE = "en-US-JennyNeural"


def _run_command(command: list[str], output_dir: Path) -> str:
    """Run an external command and return its standard output."""
    result = subprocess.run(
        command,
        cwd=output_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _audio_duration(audio_path: Path, output_dir: Path) -> float:
    """Read the actual duration of an audio file using ffprobe."""
    output = _run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            audio_path.name,
        ],
        output_dir,
    )

    data = json.loads(output)
    return round(float(data["format"]["duration"]), 2)


async def generate_narration(
    scenes: list[dict[str, Any]],
    output_dir: str | Path,
    voice: str = DEFAULT_VOICE,
) -> dict[str, Any]:
    """Generate per-scene MP3s, a combined track, and a JSON manifest."""
    if not scenes:
        raise ValueError("Cannot generate narration without scenes.")

    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to combine scene audio.")

    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe is required to measure audio duration.")

    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    manifest_scenes = []
    audio_files = []

    for scene in scenes:
        scene_number = int(scene["scene_number"])
        narration = str(scene["narration"]).strip()

        if not narration:
            raise ValueError(
                f"Scene {scene_number} has empty narration."
            )

        filename = f"scene_{scene_number:03d}.mp3"
        audio_path = destination / filename

        communicator = edge_tts.Communicate(narration, voice)
        await communicator.save(str(audio_path))

        actual_duration = _audio_duration(audio_path, destination)
        audio_files.append(filename)

        manifest_scenes.append(
            {
                "scene_number": scene_number,
                "narration": narration,
                "visual_description": scene["visual_description"],
                "estimated_duration_seconds": scene["duration_seconds"],
                "audio_duration_seconds": actual_duration,
                "audio_file": filename,
            }
        )

    concat_file = destination / "audio_files.txt"
    concat_file.write_text(
        "".join(f"file '{filename}'\n" for filename in audio_files),
        encoding="utf-8",
    )

    _run_command(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            concat_file.name,
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            "narration.mp3",
        ],
        destination,
    )

    manifest = {
        "voice": voice,
        "scene_count": len(manifest_scenes),
        "total_audio_duration_seconds": round(
            sum(
                scene["audio_duration_seconds"]
                for scene in manifest_scenes
            ),
            2,
        ),
        "combined_audio_file": "narration.mp3",
        "scenes": manifest_scenes,
    }

    manifest_path = destination / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return manifest
