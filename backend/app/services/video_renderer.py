import json
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any


WIDTH = 1280
HEIGHT = 720
FPS = 24
BACKGROUND = "0x0B1220"
ACCENT = "0x8D212A"
TEXT_COLOR = "white"
MUTED_COLOR = "0xC7CEDB"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _run(command: list[str], cwd: Path) -> str:
    """Execute FFmpeg or FFprobe and return standard output."""
    result = subprocess.run(
        command,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _escape_drawtext(value: str) -> str:
    """Escape text for use in an FFmpeg drawtext filter."""
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("\n", " ")
    )


def _write_scene_text(
    scene: dict[str, Any],
    topic: str,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write text files used by FFmpeg to render a scene card."""
    number = int(scene["scene_number"])
    narration = str(scene["narration"]).strip()

    if not narration:
        raise ValueError(f"Scene {number} has empty narration.")

    title = f"SCENE {number:02d}"
    topic_text = topic.strip() or "Explainer video"

    # Wrap text to keep it readable on a 720p frame.
    narration_text = "\n".join(textwrap.wrap(narration, width=28))
    visual_text = str(scene.get("visual_description", "")).strip()
    visual_text = "\n".join(textwrap.wrap(visual_text, width=55))

    title_path = output_dir / f"scene_{number:03d}_title.txt"
    narration_path = output_dir / f"scene_{number:03d}_text.txt"
    topic_path = output_dir / f"scene_{number:03d}_topic.txt"
    visual_path = output_dir / f"scene_{number:03d}_visual.txt"

    title_path.write_text(title, encoding="utf-8")
    narration_path.write_text(narration_text, encoding="utf-8")
    topic_path.write_text(topic_text, encoding="utf-8")
    visual_path.write_text(visual_text, encoding="utf-8")

    return narration_path, visual_path



def _visual_guide(scene: dict[str, Any]) -> tuple[str, tuple[str, str, str]]:
    """Choose a simple, scene-specific infographic using existing text."""
    content = (
        str(scene.get("narration", ""))
        + " "
        + str(scene.get("visual_description", ""))
    ).lower()

    if any(word in content for word in (
        "vaccine", "immune", "immunity", "pathogen", "antibody", "virus"
    )):
        return (
            "HOW IMMUNITY BUILDS",
            ("VACCINE SIGNAL", "IMMUNE RESPONSE", "IMMUNE MEMORY"),
        )

    if any(word in content for word in (
        "data", "analysis", "analytics", "statistics", "evidence"
    )):
        return (
            "FROM DATA TO INSIGHT",
            ("COLLECT DATA", "ANALYSE PATTERNS", "USE INSIGHTS"),
        )

    if any(word in content for word in (
        "software", "code", "program", "application", "system", "algorithm"
    )):
        return (
            "HOW A SYSTEM WORKS",
            ("INPUT", "PROCESS", "OUTPUT"),
        )

    if any(word in content for word in (
        "business", "customer", "market", "company", "service"
    )):
        return (
            "A SIMPLE WORKFLOW",
            ("IDENTIFY NEED", "DELIVER SERVICE", "CHECK RESULTS"),
        )

    if any(word in content for word in (
        "climate", "environment", "energy", "carbon", "planet"
    )):
        return (
            "UNDERSTANDING THE IMPACT",
            ("CAUSE", "CHANGE", "CONSEQUENCE"),
        )

    return (
        "KEY IDEA",
        ("THE PROBLEM", "THE MAIN IDEA", "THE OUTCOME"),
    )


def render_video(
    scenes: list[dict[str, Any]],
    narration_manifest_path: str | Path,
    output_path: str | Path,
    topic: str = "Explainer video",
) -> dict[str, Any]:
    """Render scene cards with narration into a single H.264 MP4."""
    if not scenes:
        raise ValueError("Cannot render a video without scenes.")

    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to render the video.")

    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe is required to inspect the rendered video.")

    manifest_path = Path(narration_manifest_path).resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Narration manifest not found: {manifest_path}"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_scenes = {
        int(item["scene_number"]): item
        for item in manifest.get("scenes", [])
    }

    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    work_dir = destination.parent / f"{destination.stem}_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    audio_dir = manifest_path.parent

    # Validate every scene and audio input before starting FFmpeg.
    # This avoids partial renders when a later scene is missing audio.
    for scene in scenes:
        number = int(scene["scene_number"])
        audio_info = manifest_scenes.get(number)

        if not audio_info:
            raise ValueError(
                f"Scene {number} is missing from the narration manifest."
            )

        audio_path = audio_dir / str(audio_info["audio_file"])
        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Audio for scene {number} not found: {audio_path}"
            )

        duration = float(audio_info["audio_duration_seconds"])
        if duration <= 0:
            raise ValueError(
                f"Scene {number} has an invalid audio duration."
            )

    rendered_scenes = []
    scene_results = []

    for scene in scenes:
        number = int(scene["scene_number"])
        audio_info = manifest_scenes.get(number)

        if not audio_info:
            raise ValueError(
                f"Scene {number} is missing from the narration manifest."
            )

        audio_name = str(audio_info["audio_file"])
        audio_path = audio_dir / audio_name
        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Audio for scene {number} not found: {audio_path}"
            )

        duration = float(audio_info["audio_duration_seconds"])
        if duration <= 0:
            raise ValueError(
                f"Scene {number} has an invalid audio duration."
            )

        narration_file, visual_file = _write_scene_text(
            scene, topic, work_dir
        )
        title_file = work_dir / f"scene_{number:03d}_title.txt"
        topic_file = work_dir / f"scene_{number:03d}_topic.txt"

        video_name = f"scene_{number:03d}.mp4"
        video_path = work_dir / video_name

        # Pair the narration with a simple infographic on the right.
        heading, labels = _visual_guide(scene)

        fade_out_start = max(0.0, duration - 0.35)

        filters = (
            f"drawbox=x=0:y=0:w={WIDTH}:h=12:color={ACCENT}:t=fill,"
            f"drawtext=fontfile={FONT_PATH}:textfile={topic_file}:"
            f"fontcolor={MUTED_COLOR}:fontsize=22:x=80:y=62,"
            f"drawtext=fontfile={FONT_PATH}:textfile={title_file}:"
            f"fontcolor={ACCENT}:fontsize=26:x=80:y=122,"
            f"drawtext=fontfile={FONT_PATH}:textfile={narration_file}:"
            f"fontcolor={TEXT_COLOR}:fontsize=34:line_spacing=14:"
            f"x=80:y=(h-text_h)/2,"
            f"drawtext=fontfile={FONT_PATH}:textfile={visual_file}:"
            f"fontcolor={MUTED_COLOR}:fontsize=17:x=80:y=h-100,"
            f"drawbox=x=720:y=175:w=480:h=420:"
            f"color=0x121B2E:t=fill,"
            f"drawbox=x=720:y=175:w=6:h=420:"
            f"color={ACCENT}:t=fill,"
            f"drawtext=fontfile={FONT_PATH}:text='{heading}':"
            f"fontcolor=white:fontsize=23:x=770:y=210,"
            f"drawbox=x=770:y=265:w=380:h=54:"
            f"color=0x1B2940:t=fill,"
            f"drawtext=fontfile={FONT_PATH}:text='{labels[0]}':"
            f"fontcolor=white:fontsize=21:x=800:y=282,"
            f"drawtext=fontfile={FONT_PATH}:text='v':"
            f"fontcolor={ACCENT}:fontsize=28:x=940:y=330,"
            f"drawbox=x=770:y=365:w=380:h=54:"
            f"color=0x1B2940:t=fill,"
            f"drawtext=fontfile={FONT_PATH}:text='{labels[1]}':"
            f"fontcolor=white:fontsize=21:x=800:y=382,"
            f"drawtext=fontfile={FONT_PATH}:text='v':"
            f"fontcolor={ACCENT}:fontsize=28:x=940:y=430,"
            f"drawbox=x=770:y=465:w=380:h=54:"
            f"color=0x1B2940:t=fill,"
            f"drawtext=fontfile={FONT_PATH}:text='{labels[2]}':"
            f"fontcolor=white:fontsize=21:x=800:y=482,"
            f"drawbox=x=80:y=700:w='t*80':h=5:"
            f"color={ACCENT}:t=fill,"
            f"fade=t=in:st=0:d=0.25,"
            f"fade=t=out:st={fade_out_start:.3f}:d=0.35"
        )

        _run(
            [
                "ffmpeg",
                "-y",
                "-f", "lavfi",
                "-i", f"color=c={BACKGROUND}:s={WIDTH}x{HEIGHT}:r={FPS}:d={duration}",
                "-i", str(audio_path),
                "-vf", filters,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "28",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "128k",
                "-shortest",
                "-movflags", "+faststart",
                str(video_path),
            ],
            work_dir,
        )

        rendered_scenes.append(video_name)
        scene_results.append(
            {
                "scene_number": number,
                "duration_seconds": duration,
                "video_file": video_name,
                "audio_file": audio_name,
            }
        )

    concat_file = work_dir / "video_files.txt"
    concat_file.write_text(
        "".join(f"file '{name}'\n" for name in rendered_scenes),
        encoding="utf-8",
    )

    _run(
        [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file.name,
            "-c", "copy",
            "-movflags", "+faststart",
            str(destination),
        ],
        work_dir,
    )

    probe = _run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration:format=format_name",
            "-of", "json",
            str(destination),
        ],
        work_dir,
    )
    probe_data = json.loads(probe)

    result = {
        "topic": topic,
        "output_file": str(destination),
        "width": WIDTH,
        "height": HEIGHT,
        "fps": FPS,
        "scene_count": len(scene_results),
        "duration_seconds": round(
            float(probe_data["format"]["duration"]), 2
        ),
        "format": probe_data["format"].get("format_name", "unknown"),
        "scenes": scene_results,
    }

    metadata_path = destination.with_suffix(".json")
    metadata_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return result
