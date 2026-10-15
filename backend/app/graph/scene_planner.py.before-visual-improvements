import re

from app.graph.state import VideoState


WORDS_PER_MINUTE = 130
MAX_WORDS_PER_SCENE = 32


def _split_script(script: str) -> list[str]:
    """Split narration into sentence-based segments with a word limit."""
    sentences = re.split(r"(?<=[.!?])\s+", script.strip())
    segments = []

    for sentence in sentences:
        words = sentence.split()

        if not words:
            continue

        # Split unusually long sentences into smaller narration segments.
        for start in range(0, len(words), MAX_WORDS_PER_SCENE):
            chunk = words[start : start + MAX_WORDS_PER_SCENE]
            segments.append(" ".join(chunk))

    return segments


def scene_planner_node(state: VideoState) -> dict:
    """Create a deterministic scene plan from an approved script."""
    if not state.get("approved", False):
        return {"scenes": []}

    script = state.get("script", "").strip()

    if not script:
        raise ValueError("Cannot plan scenes without an approved script.")

    segments = _split_script(script)
    scenes = []

    for number, narration in enumerate(segments, start=1):
        word_count = len(narration.split())
        duration = max(2, round(word_count / WORDS_PER_MINUTE * 60))

        scenes.append(
            {
                "scene_number": number,
                "narration": narration,
                "visual_description": (
                    "Create a clear illustration or motion graphic that "
                    "directly represents this narration without adding "
                    f"new factual claims: {narration}"
                ),
                "duration_seconds": duration,
            }
        )

    return {"scenes": scenes}
