"""Generate supported Manim clips for Physics explainer scenes."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIM = Path.home() / ".venvs/video-explainer-manim/bin/manim"
DEFAULT_TIMEOUT_SECONDS = 600

PROJECTILE_TOPIC = re.compile(r"\bprojectile(?:\s|-)*motion\b|\bprojectile\b", re.I)
PROJECTILE_SCENE = re.compile(
    r"\bprojectile\b|\btrajectory\b|\bparabolic\b|\blaunched\b|\blaunch\b|\bthrown\b",
    re.I,
)


def render_projectile_motion_clip(
    *,
    manifest_path: Path,
    output_dir: Path,
    project_root: Path | None = None,
    manim_executable: Path | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Render a projectile-motion clip and attach it to one relevant scene.

    Unsupported topics and scenes are skipped safely. The manifest's video_file
    path is relative to the repository root, as required by Remotion's prepare
    script.
    """
    root = (project_root or PROJECT_ROOT).resolve()
    manifest = Path(manifest_path).resolve()
    destination_dir = Path(output_dir).resolve()

    if not manifest.is_file():
        raise FileNotFoundError(f"Narration manifest not found: {manifest}")

    try:
        manifest.relative_to(root)
        destination_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "The manifest and Physics clip output directory must be inside "
            f"the project root: {root}"
        ) from exc

    if timeout_seconds < 1:
        raise ValueError("Manim timeout must be positive.")

    data = json.loads(manifest.read_text(encoding="utf-8"))
    topic = str(data.get("topic", "")).strip()

    if not PROJECTILE_TOPIC.search(topic):
        return {
            "status": "skipped",
            "reason": "Topic is not supported by the projectile-motion animation.",
        }

    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Narration manifest must contain at least one scene.")

    candidates = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue

        narration = str(scene.get("narration", ""))
        matches = PROJECTILE_SCENE.findall(narration)
        if matches:
            candidates.append((len(matches), scene))

    if not candidates:
        return {
            "status": "skipped",
            "reason": "No narration scene explicitly describes projectile motion.",
        }

    # Attach the clip to the scene with the strongest relevant narration match.
    _, target_scene = max(
        candidates,
        key=lambda item: (
            item[0],
            -int(item[1].get("scene_number", 999999)),
        ),
    )

    source = root / "backend/app/science/physics/projectile_motion.py"
    if not source.is_file():
        raise FileNotFoundError(f"Manim scene source not found: {source}")

    configured_executable = (
        manim_executable
        or Path(os.environ.get("MANIM_EXECUTABLE", str(DEFAULT_MANIM)))
    )
    executable = Path(configured_executable).expanduser()

    if not executable.is_file():
        raise FileNotFoundError(
            f"Manim executable not found: {executable}. "
            "Set MANIM_EXECUTABLE if Manim is installed elsewhere."
        )

    destination_dir.mkdir(parents=True, exist_ok=True)
    media_dir = destination_dir / "manim_media"
    clip_path = destination_dir / "projectile_motion.mp4"

    # Avoid accidentally accepting a stale output from an earlier run.
    shutil.rmtree(media_dir, ignore_errors=True)
    clip_path.unlink(missing_ok=True)

    command = [
        str(executable),
        "render",
        "-ql",
        "--renderer=cairo",
        "--format=mp4",
        "--media_dir",
        str(media_dir),
        "--output_file",
        "ProjectileMotion",
        str(source),
        "ProjectileMotion",
    ]

    try:
        subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Could not start the Manim rendering process.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Manim rendering exceeded {timeout_seconds} seconds."
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(
            f"Manim projectile-motion rendering failed.\n{details}"
        ) from exc

    expected_clip = (
        media_dir
        / "videos"
        / "projectile_motion"
        / "480p15"
        / "ProjectileMotion.mp4"
    )

    if expected_clip.is_file() and expected_clip.stat().st_size > 0:
        generated_clip = expected_clip
    else:
        alternatives = [
            path
            for path in (media_dir / "videos" / "projectile_motion").rglob(
                "ProjectileMotion.mp4"
            )
            if path.is_file() and path.stat().st_size > 0
        ] if (media_dir / "videos" / "projectile_motion").is_dir() else []

        if not alternatives:
            raise RuntimeError(
                "Manim finished without producing ProjectileMotion.mp4."
            )
        generated_clip = alternatives[0]

    shutil.copy2(generated_clip, clip_path)

    target_scene["video_file"] = clip_path.relative_to(root).as_posix()
    manifest.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "status": "rendered",
        "clip_file": str(clip_path),
        "scene_number": target_scene.get("scene_number"),
        "video_file": target_scene["video_file"],
    }
