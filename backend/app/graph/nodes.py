
from app.graph.state import VideoState


def research_node(state: VideoState) -> dict:
    """Provide clearly labelled placeholder research for now."""
    return {
        "research_notes": [
            (
                f"Research is pending for: {state['topic']}. "
                "This is demonstration data, not a verified fact."
            )
        ]
    }


def scriptwriter_node(state: VideoState) -> dict:
    """Create a simple deterministic draft without an LLM."""
    topic = state["topic"]

    return {
        "script": (
            f"Today we will explain {topic}. "
            "We will introduce the main idea, explain how it works, "
            "and summarize what viewers should remember."
        )
    }


def critic_node(state: VideoState) -> dict:
    """Apply a simple, explicit hook-quality rule."""
    script = state["script"]

    if not script.startswith("Imagine"):
        return {
            "critique": (
                "The opening needs a stronger curiosity-driven hook."
            ),
            "approved": False,
        }

    return {
        "critique": "The hook passed the demonstration quality check.",
        "approved": True,
    }


def revise_script_node(state: VideoState) -> dict:
    """Apply the critic's feedback to the draft."""
    script = state["script"]
    topic = state["topic"]

    if state["revision_count"] >= 2:
        return {
            "critique": "Revision limit reached.",
            "approved": False,
        }

    # Replace the opening sentence with a stronger hook.
    remainder = script.split(". ", 1)

    revised_script = (
        f"Imagine discovering something surprising about {topic}. "
        + (remainder[1] if len(remainder) > 1 else "")
    )

    return {
        "script": revised_script,
        "revision_count": state["revision_count"] + 1,
    }
