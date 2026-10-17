import json
import os
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.graph.state import VideoState
from app.graph.graph_layout import layout_scene_graph
from app.graph.remotion_adapter import to_remotion_visual
from app.graph.semantic_extractor import extract_semantic_graph


WORDS_PER_MINUTE = 130
MAX_WORDS_PER_SCENE = 32

# ---------------------------------------------------------------------------
# Pydantic models – mirror the Zod VisualSpecSchema in remotion/src/visualAdapter.ts
# ---------------------------------------------------------------------------

ProcessKind = Literal[
    "transfer", "sequence", "cycle", "mechanism",
    "structure", "contrast", "quantity", "relationships",
]

PROCESS_KIND_TO_VISUAL: dict[str, str] = {
    "transfer": "flow",
    "sequence": "sequence",
    "cycle": "cycle",
    "mechanism": "layers",
    "structure": "anatomy",
    "contrast": "comparison",
    "quantity": "bars",
    "relationships": "scene-graph",
}


class _NodeSpec(BaseModel):
    label: str
    icon: str = "dot"
    color: str | None = None


class _FlowSpec(BaseModel):
    type: Literal["flow"]
    title: str | None = None
    footnote: str | None = None
    nodes: list[_NodeSpec] = Field(min_length=2, max_length=4)


class _HubSpec(BaseModel):
    type: Literal["hub"]
    title: str | None = None
    footnote: str | None = None
    center: _NodeSpec
    satellites: list[_NodeSpec] = Field(min_length=2, max_length=6)
    direction: Literal["in", "out"] | None = None


class _BarItem(BaseModel):
    label: str
    value: float = Field(ge=0)
    color: str | None = None


class _BarsSpec(BaseModel):
    type: Literal["bars"]
    title: str | None = None
    footnote: str | None = None
    suffix: str | None = None
    bars: list[_BarItem] = Field(min_length=2, max_length=6)


class _SequenceStep(BaseModel):
    label: str
    detail: str | None = None
    icon: str | None = None


class _SequenceSpec(BaseModel):
    type: Literal["sequence"]
    title: str | None = None
    footnote: str | None = None
    steps: list[_SequenceStep] = Field(min_length=2, max_length=5)


class _CycleStage(BaseModel):
    label: str
    color: str | None = None


class _CycleSpec(BaseModel):
    type: Literal["cycle"]
    title: str | None = None
    footnote: str | None = None
    centerLabel: str | None = None
    stages: list[_CycleStage] = Field(min_length=3, max_length=6)


class _LayerItem(BaseModel):
    label: str
    note: str | None = None
    color: str | None = None


class _CarrierItem(BaseModel):
    label: str
    fromLayer: int = Field(ge=0)
    toLayer: int = Field(ge=0)
    color: str | None = None


class _LayersSpec(BaseModel):
    type: Literal["layers"]
    title: str | None = None
    footnote: str | None = None
    layers: list[_LayerItem] = Field(min_length=2, max_length=6)
    carriers: list[_CarrierItem] | None = None

    @model_validator(mode="after")
    def clamp_carrier_indexes(self) -> "_LayersSpec":
        if self.carriers:
            n = len(self.layers)
            self.carriers = [
                c for c in self.carriers
                if 0 <= c.fromLayer < n and 0 <= c.toLayer < n
            ]
        return self


class _AnatomyPart(BaseModel):
    label: str
    note: str | None = None


class _AnatomySpec(BaseModel):
    type: Literal["anatomy"]
    title: str | None = None
    footnote: str | None = None
    subject: Literal["circle", "capsule", "block", "blob"] = "blob"
    parts: list[_AnatomyPart] = Field(min_length=2, max_length=6)


class _Side(BaseModel):
    heading: str
    points: list[str] = Field(min_length=1, max_length=4)
    color: str | None = None


class _ComparisonSpec(BaseModel):
    type: Literal["comparison"]
    title: str | None = None
    footnote: str | None = None
    left: _Side
    right: _Side


class _SceneGraphNode(BaseModel):
    id: str
    label: str
    x: float = Field(ge=0, le=1000)
    y: float = Field(ge=0, le=430)
    size: float | None = None
    color: str | None = None
    appearAt: float | None = None


class _SceneGraphLink(BaseModel):
    from_: str = Field(alias="from")
    to: str
    label: str | None = None
    color: str | None = None
    style: Literal["solid", "dashed"] | None = None
    appearAt: float | None = None

    model_config = {"populate_by_name": True}


class _SceneGraphSpec(BaseModel):
    type: Literal["scene-graph"]
    title: str | None = None
    footnote: str | None = None
    nodes: list[_SceneGraphNode] = Field(min_length=2, max_length=10)
    links: list[_SceneGraphLink]
    groups: list[Any] | None = None


_VISUAL_UNION = (
    _FlowSpec | _HubSpec | _BarsSpec | _SequenceSpec | _CycleSpec
    | _LayersSpec | _AnatomySpec | _ComparisonSpec | _SceneGraphSpec
)


class _PlannerSceneOutput(BaseModel):
    concept: str
    processKind: ProcessKind
    visual: dict[str, Any]


# ---------------------------------------------------------------------------
# Gemini visual planner
# ---------------------------------------------------------------------------

_PLANNER_SYSTEM = """
You are an educational visual planner. Given a scene's narration, you classify it
and design one visual diagram for Remotion to render.

For EACH scene, return JSON with exactly these fields:
1. concept: the single idea this scene's narration teaches (one sentence).
2. processKind: one of transfer | sequence | cycle | mechanism | structure | contrast | quantity | relationships
3. visual: a spec of the matching type.

Mapping (use the left side to pick the visual type):
  transfer      → flow
  sequence      → sequence
  cycle         → cycle
  mechanism     → layers
  structure     → anatomy
  contrast      → comparison
  quantity      → bars
  relationships → scene-graph   (LAST RESORT — every node needs x/y)
  hub is also valid for one thing with several inputs or outputs.

Rules:
- Choose per scene from the concept. The video's overall topic is NOT a factor.
- Do NOT use the same visual type for consecutive scenes unless their processKind is genuinely the same.
- Labels: max 3 words, UPPERCASE for node labels. Footnote: one factual sentence.
- Only use facts from the narration. Never invent numbers.
- Every scene needs a title (max 6 words).
- Icons must come from: sun, panel, cell, bolt, inverter, house, syringe, virus, immune, shield, antibody, rna, protein, gear, link, check, dot, heart, or be omitted.
- Colors must be one of: teal, gold, red, purple, white.

Type constraints:
- flow: 2-4 nodes. hub: center + 2-6 satellites. cycle: 3-6 stages. sequence: 2-5 steps (label + one-line detail).
- layers: 2-6 layers listed TOP to BOTTOM; carriers use 0-based layer indexes.
- anatomy: subject is circle|capsule|block|blob, 2-6 parts, each with a short note.
- comparison: left/right each have a heading and 1-4 short points.
- bars: 2-6 bars with numeric values taken from the narration only.
- scene-graph: LAST RESORT only. Every node needs x (0-1000) and y (0-430).
- illustration: do not use.
""".strip()


def _call_gemini_planner(
    scenes: list[dict],
    topic: str,
) -> list[dict[str, Any] | None]:
    """Call Gemini once to plan visuals for all scenes.

    Returns a list parallel to `scenes` where each entry is either a dict
    with concept/processKind/visual, or None if planning failed for that scene.
    A failure on one scene never fails the whole call.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        return [None] * len(scenes)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return [None] * len(scenes)

    scenes_text = "\n\n".join(
        f"Scene {s['scene_number']}:\n{s['narration']}"
        for s in scenes
    )

    prompt = (
        f"Topic (for context only – do NOT let it bias visual-type selection):\n{topic}\n\n"
        f"Scenes:\n{scenes_text}\n\n"
        "Return a JSON array, one object per scene in order, each with fields: "
        "concept, processKind, visual. "
        "If you cannot design a valid visual for a scene, set visual to null."
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite"),
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=_PLANNER_SYSTEM,
                response_mime_type="application/json",
                temperature=0.3,
                max_output_tokens=4096,
            ),
        )
        raw = json.loads(response.text or "[]")
    except Exception as exc:
        print(f"[visual-planner] Gemini call failed: {exc}")
        return [None] * len(scenes)

    if not isinstance(raw, list):
        print("[visual-planner] Gemini returned non-list; discarding all visuals")
        return [None] * len(scenes)

    results: list[dict[str, Any] | None] = []
    for i, item in enumerate(raw[:len(scenes)]):
        scene_num = scenes[i]["scene_number"] if i < len(scenes) else i + 1
        if not isinstance(item, dict):
            results.append(None)
            continue
        # Validate + normalise per scene – a bad spec for one scene must never
        # raise; we just drop it and let Remotion fall back to legacy routing.
        try:
            parsed = _PlannerSceneOutput.model_validate(item)
        except Exception as exc:
            print(f"[visual-planner] scene {scene_num} failed validation: {exc}")
            results.append(None)
            continue

        # Now validate the visual dict against the per-type Pydantic model.
        visual_dict = parsed.visual
        validated_visual: dict[str, Any] | None = None
        if isinstance(visual_dict, dict):
            try:
                vtype = visual_dict.get("type")
                _model_map: dict[str, type[BaseModel]] = {
                    "flow": _FlowSpec, "hub": _HubSpec, "bars": _BarsSpec,
                    "sequence": _SequenceSpec, "cycle": _CycleSpec,
                    "layers": _LayersSpec, "anatomy": _AnatomySpec,
                    "comparison": _ComparisonSpec, "scene-graph": _SceneGraphSpec,
                }
                if vtype in _model_map:
                    validated = _model_map[vtype].model_validate(visual_dict)
                    validated_visual = validated.model_dump(exclude_none=True, by_alias=True)
                    # Pydantic renames from_ back to from for scene-graph links
                    if vtype == "scene-graph" and "links" in validated_visual:
                        for lnk in validated_visual["links"]:
                            if "from_" in lnk and "from" not in lnk:
                                lnk["from"] = lnk.pop("from_")
            except Exception as exc:
                print(f"[visual-planner] scene {scene_num} visual invalid: {exc}")

        results.append({
            "concept": parsed.concept,
            "processKind": parsed.processKind,
            "visual": validated_visual,  # may be None → Remotion fallback
        })

    # Pad if Gemini returned fewer items than scenes
    while len(results) < len(scenes):
        results.append(None)

    return results


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


def _semantic_visual(narration: str) -> dict | None:
    """Build a Remotion visual through the semantic graph pipeline."""
    graph = extract_semantic_graph(narration)

    if graph is None:
        return None

    try:
        positioned_graph = layout_scene_graph(graph)
        return to_remotion_visual(positioned_graph)
    except (ValueError, TypeError, KeyError):
        # Invalid or unlayoutable graphs should not break video generation.
        return None


def scene_planner_node(
    state: VideoState,
    *,
    use_semantic_graph: bool = False,
    use_gemini_planner: bool = False,
) -> dict:
    """Create a scene plan from an approved script.

    When use_gemini_planner is True (and GEMINI_API_KEY is set), Gemini is
    called once to plan visuals for all scenes.  Per-scene failures are caught
    and fall back to the existing deterministic planner.
    """
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

        scene: dict[str, Any] = {
            "scene_number": number,
            "narration": narration,
            "visual_description": _visual_description(topic, narration),
            "duration_seconds": duration,
        }

        visual: dict[str, Any] | None = None

        if use_semantic_graph:
            visual = _semantic_visual(narration)

        # Preserve the existing deterministic visual planner as the fallback.
        if visual is None:
            visual = _structured_visual(narration)

        if visual is not None:
            scene["visual"] = visual

        scenes.append(scene)

    # ── Gemini intelligent visual planner ────────────────────────────────────
    # Runs after the deterministic pass so any validated planner result wins.
    if use_gemini_planner:
        planner_results = _call_gemini_planner(scenes, topic)
        for scene, plan in zip(scenes, planner_results):
            sn = scene["scene_number"]
            if plan is None:
                print(f"[visual-planner] scene {sn}: no planner output, keeping legacy")
                continue
            # Write concept + processKind into the scene (Remotion ignores them)
            scene["concept"] = plan["concept"]
            scene["processKind"] = plan["processKind"]
            validated_visual = plan.get("visual")
            if validated_visual is not None:
                scene["visual"] = validated_visual
                print(
                    f"[visual-planner] scene {sn}: {plan['processKind']} "
                    f"→ {validated_visual.get('type', '?')}"
                )
            else:
                print(
                    f"[visual-planner] scene {sn}: planner visual invalid, "
                    "keeping legacy"
                )

    return {"scenes": scenes}
