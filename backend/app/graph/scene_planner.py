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

        for start in range(0, len(words), MAX_WORDS_PER_SCENE):
            chunk = words[start : start + MAX_WORDS_PER_SCENE]
            segments.append(" ".join(chunk))

    return segments


def _visual_description(topic: str, narration: str) -> str:
    """Describe a scene using its topic and actual narration."""
    text = f"{topic} {narration}".lower()
    topic_text = topic.lower()

    # Handle water-cycle topics before keyword branches such as solar.
    if "water cycle" in topic_text:
        narration_lower = narration.lower()

        if "evaporation" in narration_lower or "evaporate" in narration_lower:
            focus = "sunlight driving evaporation from surface water"
        elif any(term in narration_lower for term in (
            "condens", "cloud", "droplet",
        )):
            focus = "water vapour cooling and condensing into clouds"
        elif "precipitation" in narration_lower or "rain" in narration_lower:
            focus = "water returning to the surface as precipitation"
        else:
            focus = "the movement of water through the water cycle"

        return (
            "Educational water-cycle illustration focused on "
            f"{focus}, using clear labels and simple process elements."
        )

    # Heart circulation: describe the relationship narrated in this scene.
    if re.search(r"\bheart\b|\bcardiac\b", text):
        if re.search(
            r"venae cavae|returning from the body|enters the right side",
            narration,
            re.IGNORECASE,
        ):
            focus = (
                "blood returning from the body and entering the right "
                "side of the heart through the venae cavae"
            )
        elif re.search(
            r"pulmonary artery|right side.*lungs|blood to the lungs",
            narration,
            re.IGNORECASE,
        ):
            focus = (
                "the right side of the heart sending blood toward the "
                "lungs through the pulmonary artery"
            )
        elif re.search(
            r"left side|returning from the lungs|receives blood",
            narration,
            re.IGNORECASE,
        ):
            focus = (
                "blood returning from the lungs and entering the left "
                "side of the heart"
            )
        elif re.search(
            r"four chambers|four valves|muscular organ|anatomy",
            narration,
            re.IGNORECASE,
        ):
            focus = (
                "a clearly labelled heart with four chambers and the "
                "valves mentioned in the narration"
            )
        elif re.search(
            r"oxygen|nutrients|carbon dioxide|blood vessels|tissues",
            narration,
            re.IGNORECASE,
        ):
            focus = (
                "blood moving through vessels and carrying the oxygen, "
                "nutrients, or waste products named in the narration"
            )
        else:
            focus = "the heart and the specific blood-flow idea being explained"

        return (
            f"Illustrate {focus}. Use a simple, clearly labelled "
            "educational motion graphic. Show directional arrows only "
            "for blood-flow relationships supported by the narration. "
            f"Scene narration: {narration} Do not invent measurements "
            "or unrelated anatomical details."
        )

    # Vaccine concepts: match the idea being narrated, not a fixed
    # scene number. Keep descriptions illustrative rather than factual
    # additions to the approved script.
    if re.search(r"\bvaccin\w*|\bimmuni[sz]ation\b", text):
        if re.search(
            r"memory|remember|future exposure|in the future|later",
            narration,
            re.IGNORECASE,
        ):
            focus = (
                "immune memory and readiness for a possible future exposure"
            )
        elif re.search(
            r"mrna|messenger rna|protein|cellular instructions",
            narration,
            re.IGNORECASE,
        ):
            focus = "the mRNA instructions and protein concept mentioned"
        elif re.search(
            r"antibod|antigen|recogniz|recognis|receptor|bind",
            narration,
            re.IGNORECASE,
        ):
            focus = "the antigen recognition or antibody concept mentioned"
        elif re.search(
            r"immune system|immune cell|defen[cs]e|respond|response",
            narration,
            re.IGNORECASE,
        ):
            focus = "the immune-system response described"
        else:
            focus = "the vaccine concept described in the narration"

        return (
            f"Illustrate {focus}. Use a simple, clearly labelled "
            "scientific motion graphic that matches this scene's narration. "
            f"Scene narration: {narration} Do not add medical claims."
        )

    # Solar concepts: prefer the mechanism or component actually discussed.
    if re.search(r"solar|photovoltaic|sunlight", text):
        if re.search(
            r"batter(?:y|ies)|stor(?:e|es|ed|ing)|storage",
            narration,
            re.IGNORECASE,
        ):
            focus = "solar electricity storage and the battery concept mentioned"
        elif re.search(
            r"inverter|alternating current|\bAC\b",
            narration,
            re.IGNORECASE,
        ):
            focus = "the inverter or AC-conversion concept mentioned"
        elif re.search(
            r"electron|electrical circuit|direct current|\bDC\b",
            narration,
            re.IGNORECASE,
        ):
            focus = "the electrical process described in the solar cell"
        elif re.search(
            r"silicon|photovoltaic effect|solar cell|solar cells",
            narration,
            re.IGNORECASE,
        ):
            focus = "the solar-cell mechanism described"
        elif re.search(
            r"home|house|lamp|lighting|appliance|device",
            narration,
            re.IGNORECASE,
        ):
            focus = "the solar-powered use or application described"
        else:
            focus = "the sunlight-to-electricity concept described"

        return (
            f"Illustrate {focus}. Show only relevant solar components "
            "and the relationships described in the narration. "
            f"Scene narration: {narration} Do not invent system components."
        )

    return (
        "Illustrate the specific idea in this scene with a simple, "
        "clearly labelled diagram or motion graphic. Focus on the entities "
        "and relationships stated or directly implied by the narration. "
        f"Scene narration: {narration} Avoid unrelated topic diagrams, "
        "invented data, and unsupported factual claims."
    )



def _visual_label(text: str) -> str:
    """Create a short display label from words actually present in narration."""
    text = re.sub(r"^[\s,;:]+|[\s,;:]+$", "", text)
    text = re.sub(r"^(?:the|a|an|this|that)\s+", "", text, flags=re.IGNORECASE)
    words = re.findall(r"[A-Za-z0-9'-]+", text)
    return " ".join(words[:3]).upper()



def _water_cycle_visual(narration: str) -> dict | None:
    """Recognize a few explicit water-cycle relationships."""
    patterns = [
        (
            r"\bwater\b.*?\ballowing\s+some\s+of\s+it\s+"
            r"to\s+evaporate\b.*?\bas\s+water\s+vapou?r\b",
            "WATER",
            "WATER VAPOUR",
            "EVAPORATES INTO",
        ),
        (
            r"\bwater\b.*?\bfall\s+back\b.*?\bas\s+precipitation\b",
            "WATER",
            "PRECIPITATION",
            "FALLS AS",
        ),
        (
            r"\bvapou?r\b.*?\bcondense\s+into\s+tiny\s+water\s+"
            r"droplets\b",
            "VAPOUR",
            "TINY WATER DROPLETS",
            "CONDENSES INTO",
        ),
    ]

    for pattern, left, right, relationship in patterns:
        if not re.search(pattern, narration, re.IGNORECASE):
            continue

        return {
            "type": "scene-graph",
            "title": "How the Water Cycle Works",
            "nodes": [
                {
                    "id": "source",
                    "label": left,
                    "x": 300,
                    "y": 175,
                    "size": 38,
                    "color": "#4FD1C5",
                    "appearAt": 0.2,
                },
                {
                    "id": "outcome",
                    "label": right,
                    "x": 700,
                    "y": 175,
                    "size": 38,
                    "color": "#F2B84B",
                    "appearAt": 0.45,
                },
            ],
            "links": [
                {
                    "from": "source",
                    "to": "outcome",
                    "label": relationship,
                    "color": "#4FD1C5",
                    "style": "solid",
                    "appearAt": 0.4,
                }
            ],
            "footnote": "Relationship identified from the narration",
        }

    return None


def _structured_visual(narration: str) -> dict | None:
    """Build a positioned scene graph from an explicit narration relationship.

    The planner stays conservative: it creates a graph only when the narration
    provides a recognizable subject and outcome.
    """
    water_cycle_visual = _water_cycle_visual(narration)
    if water_cycle_visual:
        return water_cycle_visual

    patterns = [
        (
            r"(?P<left>[^.!?;]{2,55}?),?\s+"
            r"(?P<verb>causing)\s+"
            r"(?P<right>[^.!?;,]{2,55})"
        ),
        (
            r"(?P<left>[^.!?;]{2,55}?)\s+"
            r"(?P<verb>releases?)\s+"
            r"(?P<right>[^.!?;,]{2,55})"
        ),
        (
            r"(?P<left>[^.!?;]{2,55}?)\s+cools\s+and\s+"
            r"(?P<action>condenses\s+into)\s+"
            r"(?P<right>[^.!?;,]{2,55})"
        ),
        (
            r"(?P<left>[^.!?;]{2,55}?)\s+"
            r"(?:cools|heats|evaporates|condenses)\s+and\s+"
            r"(?P<action>forms|creates|produces)\s+"
            r"(?P<right>[^.!?;]{2,55})"
        ),
        (
            r"(?P<left>[^.!?;]{2,55}?)\s+"
            r"(?P<verb>causes|leads to|produces|forms|creates|"
            r"increases|reduces|raises|lowers|converts?)\s+"
            r"(?P<right>[^.!?;]{2,55})"
        ),
    ]

    for pattern in patterns:
        match = re.search(pattern, narration, re.IGNORECASE)
        if not match:
            continue

        left = _visual_label(match.group("left"))
        right = _visual_label(match.group("right"))

        # Avoid generic pronouns and labels too short to be useful.
        if (
            len(left) < 2
            or len(right) < 2
            or left.lower() in {"this", "that", "it", "they", "we"}
            or right.lower() in {"this", "that", "it", "they", "we"}
            or left == right
        ):
            continue

        relationship = match.groupdict().get("verb") or match.groupdict().get("action") or "forms"
        if relationship.lower() == "causing":
            relationship = "causes"

        return {
            "type": "scene-graph",
            "title": "How the Ideas Connect",
            "nodes": [
                {
                    "id": "source",
                    "label": left,
                    "x": 300,
                    "y": 175,
                    "size": 38,
                    "color": "#4FD1C5",
                    "appearAt": 0.2,
                },
                {
                    "id": "outcome",
                    "label": right,
                    "x": 700,
                    "y": 175,
                    "size": 38,
                    "color": "#F2B84B",
                    "appearAt": 0.45,
                },
            ],
            "links": [
                {
                    "from": "source",
                    "to": "outcome",
                    "label": relationship.upper(),
                    "color": "#4FD1C5",
                    "style": "solid",
                    "appearAt": 0.4,
                }
            ],
            "footnote": "Relationship identified from the narration",
        }

    return None

def scene_planner_node(state: VideoState) -> dict:
    """Create a deterministic scene plan from an approved script."""
    if not state.get("approved", False):
        return {"scenes": []}

    script = state.get("script", "").strip()

    if not script:
        raise ValueError("Cannot plan scenes without an approved script.")

    topic = str(state.get("topic", "")).strip()
    segments = _split_script(script)
    scenes = []

    for number, narration in enumerate(segments, start=1):
        word_count = len(narration.split())
        duration = max(2, round(word_count / WORDS_PER_MINUTE * 60))

        scene = {
            "scene_number": number,
            "narration": narration,
            "visual_description": _visual_description(topic, narration),
            "duration_seconds": duration,
        }

        visual = _structured_visual(narration)
        if visual is not None:
            scene["visual"] = visual

        scenes.append(scene)

    return {"scenes": scenes}
