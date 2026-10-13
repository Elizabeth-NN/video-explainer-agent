
import os
from pathlib import Path

from dotenv import load_dotenv

from app.graph.state import VideoState

# Load the backend/.env file regardless of the directory used to run Python.
BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


def research_node(state: VideoState) -> dict:
    """Placeholder research until source-backed research is implemented."""
    return {
        "research_notes": [
            (
                f"Research is pending for: {state['topic']}. "
                "This is demonstration data, not a verified fact."
            )
        ]
    }


def scriptwriter_node(state: VideoState) -> dict:
    """Deterministic scriptwriter for testing without API calls."""
    topic = state["topic"]
    return {
        "script": (
            f"Today we will explain {topic}. "
            "We will introduce the main idea, explain how it works, "
            "and summarize what viewers should remember."
        )
    }


def gemini_scriptwriter_node(state: VideoState) -> dict:
    """Generate an explainer script using Google's Gemini API."""
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    if not api_key or not api_key.strip():
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Add it to backend/.env."
        )

    from google import genai
    from google.genai import types

    research_notes = "\n".join(state["research_notes"])

    system_instruction = """
You are an explainer-video scriptwriter.

Write an engaging, clear explainer script for a general audience.
Start the script with the word "Imagine".
Aim for approximately 100–150 words.
Use simple language and a logical sequence.
Explain unfamiliar terms clearly.
Do not invent statistics, quotations, sources, or citations.
The supplied research notes may be placeholders, not verified facts.
Do not present unsupported claims as verified facts.
Return only the script, without a title or extra commentary.
""".strip()

    prompt = (
        f"Topic: {state['topic']}\n\n"
        f"Available research notes:\n{research_notes}\n\n"
        "Write the explainer-video script."
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.4,
                max_output_tokens=1200,
            ),
        )
    except Exception as exc:
        raise RuntimeError(
            "Gemini script generation failed. Check your API key, "
            "model availability, internet connection, and API quota. "
            f"Details: {exc}"
        ) from exc

    script = (response.text or "").strip()

    if not script:
        raise RuntimeError(
            "Gemini returned an empty script. Try the request again."
        )

    return {"script": script}


def critic_node(state: VideoState) -> dict:
    """Basic quality check; this is not a full fact-check."""
    script = state["script"]

    if not script.startswith("Imagine"):
        return {
            "critique": (
                "The opening needs a stronger curiosity-driven hook "
                "beginning with 'Imagine'."
            ),
            "approved": False,
        }

    return {
        "critique": "The hook passed the demonstration quality check.",
        "approved": True,
    }


def revise_script_node(state: VideoState) -> dict:
    """Apply a simple deterministic revision."""
    script = state["script"]
    topic = state["topic"]

    if state["revision_count"] >= 2:
        return {
            "critique": "Revision limit reached.",
            "approved": False,
        }

    remainder = script.split(". ", 1)
    revised_script = (
        f"Imagine discovering something surprising about {topic}. "
        + (remainder[1] if len(remainder) > 1 else "")
    )

    return {
        "script": revised_script,
        "revision_count": state["revision_count"] + 1,
    }
