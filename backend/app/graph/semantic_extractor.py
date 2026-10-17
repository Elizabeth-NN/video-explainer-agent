"""Extract renderer-independent semantic graphs from narration."""

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .scene_graph import validate_scene_graph

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


def extract_semantic_graph(narration: str) -> dict[str, Any] | None:
    """Use Gemini to extract explicit concepts and relationships.

    Returns a validated semantic graph, or None if extraction is unavailable
    or the response cannot be validated. This function never performs layout.
    """
    narration = narration.strip()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not narration or not api_key:
        return None

    from google import genai
    from google.genai import types

    model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    prompt = f"""
Extract a small semantic graph from the narration below.

Return only a JSON object with this exact structure:
{{
  "schema_version": 1,
  "nodes": [
    {{"id": "short_id", "label": "Human-readable concept"}}
  ],
  "edges": [
    {{
      "source": "existing_node_id",
      "target": "existing_node_id",
      "relationship": "causes"
    }}
  ]
}}

Rules:
- Extract only concepts and relationships explicitly supported by the narration.
- Do not invent missing steps, causes, outcomes, or scientific facts.
- Use concise, meaningful labels and unique, lowercase node IDs.
- Every edge must reference IDs in the nodes list.
- Use only these relationship values:
  causes, influences, increases, decreases, transforms, contains,
  part_of, precedes, follows, connects_to, flows_to, enables,
  inhibits, feedback_to, unknown.
- Use at most 12 nodes and 20 edges.
- Prefer a small, accurate graph over a large speculative one.
- If no meaningful relationship is supported, return empty nodes and edges.
- Do not include coordinates, colors, animation instructions, or renderer data.

Narration:
{narration}
""".strip()

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=1000,
                response_mime_type="application/json",
            ),
        )

        text = (response.text or "").strip()
        if not text:
            return None

        graph = json.loads(text)

        # An empty graph is a valid signal that no reliable relationship
        # could be extracted. It should not be sent to the layout engine.
        if (
            isinstance(graph, dict)
            and graph.get("schema_version") == 1
            and graph.get("nodes") == []
            and graph.get("edges") == []
        ):
            return None

        validate_scene_graph(graph)
        return graph

    except Exception as exc:
        logger.warning("Semantic graph extraction failed: %s", exc)
        return None
