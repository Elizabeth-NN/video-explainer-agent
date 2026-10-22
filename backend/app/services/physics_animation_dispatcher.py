"""Dispatch supported Physics narration scenes to dedicated Manim animations."""

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


ANIMATIONS = (
    {
        "key": "projectile_motion",
        "source": "projectile_motion.py",
        "scene_class": "ProjectileMotion",
        "topic_pattern": re.compile(
            r"\bprojectile(?:[\s-]+motion)?\b|\btrajectory\b",
            re.I,
        ),
        "scene_pattern": re.compile(
            r"\bprojectile\b|\btrajectory\b|\bparabolic\b|"
            r"\blaunched\b|\blaunch\b|\bthrown\b",
            re.I,
        ),
    },
    {
        "key": "free_fall",
        "source": "free_fall.py",
        "scene_class": "FreeFall",
        "topic_pattern": re.compile(
            r"\bfree[\s-]*fall\b|\bfalling object\b",
            re.I,
        ),
        "scene_pattern": re.compile(
            r"\bfree[\s-]*fall\b|\bfalling object\b|\bdropped object\b|"
            r"\bfalls? under gravity\b|\bdropped from\b|"
            r"\bacceleration due to gravity\b",
            re.I,
        ),
    },
    {
        "key": "newtons_second_law",
        "source": "newtons_second_law.py",
        "scene_class": "NewtonsSecondLaw",
        "topic_pattern": re.compile(
            r"\bnewton(?:'s)? second law\b|"
            r"\bsecond law of motion\b|\bforce and acceleration\b",
            re.I,
        ),
        "scene_pattern": re.compile(
            r"\bnewton(?:'s)? second law\b|\bF\s*=\s*ma\b|"
            r"\bnet force\b|\bfree.body\b|\bfriction\b|\btension\b|"
            r"\bforce\b.{0,60}\bmass\b|\bmass\b.{0,60}\bforce\b|"
            r"\bforce\b.{0,60}\bacceleration\b|"
            r"\bacceleration\b.{0,60}\bforce\b",
            re.I,
        ),
    },
    {
        "key": "potential_energy",
        "source": "potential_energy.py",
        "scene_class": "PotentialEnergy",
        "topic_pattern": re.compile(
            r"\bpotential energy\b|\bgravitational potential\b|\bmgh\b",
            re.I,
        ),
        "scene_pattern": re.compile(
            r"\bpotential energy\b|\bgravitational potential\b|\bmgh\b|"
            r"\bheight\b.{0,50}\benergy\b|\benergy\b.{0,50}\bheight\b",
            re.I,
        ),
    },
    {
        "key": "kinematics",
        "source": "kinematics.py",
        "scene_class": "Kinematics",
        "topic_pattern": re.compile(
            r"\bkinematics\b|\bconstant acceleration\b|"
            r"\bvelocity(?:\s+and\s+time)?\b|\bdisplacement\b",
            re.I,
        ),
        "scene_pattern": re.compile(
            r"\bkinematics\b|\bvelocity\b|\bacceleration\b|"
            r"\bdisplacement\b|\bspeed\b|\bposition[- ]time\b|"
            r"\bvelocity[- ]time\b|\bconstant acceleration\b",
            re.I,
        ),
    },
)


def _find_animation(text: str, *, by_topic: bool = False) -> dict[str, Any] | None:
    """Return the first supported animation matching topic or narration."""
    pattern_key = "topic_pattern" if by_topic else "scene_pattern"

    for animation in ANIMATIONS:
        if animation[pattern_key].search(text):
            return animation

    return None


def _render_animation(
    *,
    animation: dict[str, Any],
    root: Path,
    destination_dir: Path,
    executable: Path,
    timeout_seconds: int,
) -> Path:
    """Render one animation and return its copied MP4 path."""
    source = root / "backend/app/science/physics" / animation["source"]

    if not source.is_file():
        raise FileNotFoundError(f"Manim scene source not found: {source}")

    key = animation["key"]
    scene_class = animation["scene_class"]

    media_dir = destination_dir / "manim_media" / key
    clip_path = destination_dir / f"{key}.mp4"

    shutil.rmtree(media_dir, ignore_errors=True)
    clip_path.unlink(missing_ok=True)
    media_dir.mkdir(parents=True, exist_ok=True)

    command = [
        str(executable),
        "render",
        "-ql",
        "--renderer=cairo",
        "--format=mp4",
        "--media_dir",
        str(media_dir),
        "--output_file",
        scene_class,
        str(source),
        scene_class,
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
            f"Manim rendering for {key} exceeded {timeout_seconds} seconds."
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(f"Manim rendering for {key} failed.\n{details}") from exc

    video_root = media_dir / "videos" / source.stem
    expected = video_root / "480p15" / f"{scene_class}.mp4"

    if expected.is_file() and expected.stat().st_size > 0:
        generated = expected
    else:
        alternatives = (
            [
                path
                for path in video_root.rglob(f"{scene_class}.mp4")
                if path.is_file() and path.stat().st_size > 0
            ]
            if video_root.is_dir()
            else []
        )

        if not alternatives:
            raise RuntimeError(
                f"Manim finished without producing {scene_class}.mp4."
            )

        generated = alternatives[0]

    shutil.copy2(generated, clip_path)
    return clip_path


def render_physics_clips(
    *,
    manifest_path: Path,
    output_dir: Path,
    project_root: Path | None = None,
    manim_executable: Path | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Render supported Manim animations and attach them to relevant scenes.

    A given animation is rendered once per run and reused for every narration
    scene classified as that animation. Unmatched scenes are reported so they
    can be supported explicitly later instead of being mistaken for Manim clips.
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
    scenes = data.get("scenes")

    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Narration manifest must contain at least one scene.")

    assignments: dict[str, list[dict[str, Any]]] = {}
    unmatched: list[dict[str, Any]] = []

    for scene in scenes:
        if not isinstance(scene, dict):
            continue

        narration = str(scene.get("narration", ""))
        animation = _find_animation(narration)

        if animation is None:
            unmatched.append(
                {
                    "scene_number": scene.get("scene_number"),
                    "narration": narration[:140],
                }
            )
            continue

        assignments.setdefault(animation["key"], []).append(scene)

    # If narration is too general to classify any scene, use the topic only
    # as a fallback for the first scene. Do not apply a topic-level animation
    # to every scene indiscriminately.
    if not assignments:
        topic = str(data.get("topic", "")).strip()
        animation = _find_animation(topic, by_topic=True)

        if animation is not None:
            target_scene = next(
                (scene for scene in scenes if isinstance(scene, dict)),
                None,
            )
            if target_scene is not None:
                assignments[animation["key"]] = [target_scene]
                unmatched = [
                    item for item in unmatched
                    if item["scene_number"] != target_scene.get("scene_number")
                ]

    if not assignments:
        supported = ", ".join(item["key"] for item in ANIMATIONS)
        return {
            "status": "skipped",
            "reason": (
                f"No supported Manim animation matched topic "
                f"{data.get('topic', '')!r} or its narration scenes. "
                f"Supported animations: {supported}."
            ),
            "clips": [],
            "unsupported_scenes": unmatched,
        }

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
    rendered_clips = []

    for animation in ANIMATIONS:
        key = animation["key"]
        target_scenes = assignments.get(key)

        if not target_scenes:
            continue

        clip_path = _render_animation(
            animation=animation,
            root=root,
            destination_dir=destination_dir,
            executable=executable,
            timeout_seconds=timeout_seconds,
        )
        relative_clip = clip_path.relative_to(root).as_posix()

        for scene in target_scenes:
            scene["video_file"] = relative_clip

        rendered_clips.append(
            {
                "animation": key,
                "clip_file": str(clip_path),
                "video_file": relative_clip,
                "scene_numbers": [
                    scene.get("scene_number") for scene in target_scenes
                ],
            }
        )

    manifest.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "status": "rendered",
        "clips": rendered_clips,
        "unsupported_scenes": unmatched,
    }
