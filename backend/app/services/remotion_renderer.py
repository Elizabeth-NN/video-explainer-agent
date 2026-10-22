"""Render explainer videos using Remotion."""

import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RENDER_TIMEOUT_SECONDS = 1800
REMOTION_TIMEOUT_MS = 300000


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    stage: str,
) -> subprocess.CompletedProcess:
    """Run a renderer command and provide useful errors when it fails."""
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Remotion {stage} failed: executable not found: {command[0]}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Remotion {stage} exceeded its {timeout}-second timeout."
        ) from exc
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or str(exc)).strip()
        raise RuntimeError(
            f"Remotion {stage} failed with exit code {exc.returncode}.\n"
            f"{details}"
        ) from exc


def render_remotion_video(
    *,
    manifest_path: Path,
    output_path: Path,
    project_root: Path | None = None,
    concurrency: int = 1,
    timeout_seconds: int = DEFAULT_RENDER_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Prepare the narration manifest and render the Remotion Explainer composition.

    The manifest must be inside the project root because prepare.mjs resolves
    its input paths relative to that root.
    """
    root = (project_root or PROJECT_ROOT).resolve()
    remotion_dir = root / "remotion"
    manifest = Path(manifest_path).resolve()
    output = Path(output_path).resolve()

    if not manifest.is_file():
        raise FileNotFoundError(f"Narration manifest not found: {manifest}")

    if not remotion_dir.is_dir():
        raise FileNotFoundError(f"Remotion directory not found: {remotion_dir}")

    try:
        relative_manifest = manifest.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "The narration manifest must be inside the video-explainer-agent "
            f"project directory: {root}"
        ) from exc

    if concurrency < 1:
        raise ValueError("Remotion concurrency must be at least 1.")

    if timeout_seconds < 1:
        raise ValueError("Render timeout must be positive.")

    with manifest.open("r", encoding="utf-8") as file:
        manifest_data = json.load(file)

    scenes = manifest_data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("Narration manifest must contain at least one scene.")

    output.parent.mkdir(parents=True, exist_ok=True)

    env = {
        **__import__("os").environ,
        "REMOTION_MANIFEST_PATH": relative_manifest.as_posix(),
    }

    # Prepare Remotion props and copy the manifest's audio/video assets.
    _run_command(
        ["node", "scripts/prepare.mjs"],
        cwd=remotion_dir,
        env=env,
        timeout=180,
        stage="preparation",
    )

    # Render the existing Explainer composition. Keep concurrency low for
    # machines with limited RAM; the browser startup timeout is configurable.
    _run_command(
        [
            "npx",
            "remotion",
            "render",
            "src/index.ts",
            "Explainer",
            str(output),
            "--props=./input-props.json",
            f"--concurrency={concurrency}",
            f"--timeout={REMOTION_TIMEOUT_MS}",
        ],
        cwd=remotion_dir,
        env=env,
        timeout=timeout_seconds,
        stage="video rendering",
    )

    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(
            f"Remotion completed without producing a usable MP4: {output}"
        )

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError(
            "ffprobe is required to read the rendered video's metadata."
        )

    probe = _run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height,r_frame_rate",
            "-of",
            "json",
            str(output),
        ],
        cwd=remotion_dir,
        env=env,
        timeout=60,
        stage="metadata inspection",
    )

    try:
        probe_data = json.loads(probe.stdout)
        video_stream = next(
            stream
            for stream in probe_data["streams"]
            if stream.get("codec_type") == "video"
        )
        duration = float(probe_data["format"]["duration"])
        fps = float(Fraction(video_stream["r_frame_rate"]))
        width = int(video_stream["width"])
        height = int(video_stream["height"])
    except (KeyError, StopIteration, TypeError, ValueError, ZeroDivisionError) as exc:
        raise RuntimeError(
            f"Could not read video metadata from Remotion output: {output}"
        ) from exc

    metadata = {
        "renderer": "remotion",
        "output_file": str(output),
        "width": width,
        "height": height,
        "fps": fps,
        "duration_seconds": round(duration, 3),
        "scene_count": len(scenes),
        "topic": manifest_data.get("topic", ""),
    }

    metadata_path = output.with_suffix(".json")
    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    return metadata
