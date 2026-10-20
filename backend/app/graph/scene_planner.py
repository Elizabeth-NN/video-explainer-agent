import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.graph.state import VideoState
from app.graph.graph_layout import layout_scene_graph
from app.graph.remotion_adapter import to_remotion_visual
from app.graph.semantic_extractor import extract_semantic_graph


WORDS_PER_MINUTE = 130
MAX_WORDS_PER_SCENE = 32

# ---------------------------------------------------------------------------
# Load the planner catalog (written by `npx tsx src/visuals/export_catalog.ts`)
# ---------------------------------------------------------------------------

_CATALOG_PATH = Path(__file__).resolve().parents[3] / "planner_catalog.txt"
try:
    _PLANNER_CATALOG = _CATALOG_PATH.read_text("utf-8")
except FileNotFoundError:
    _PLANNER_CATALOG = ""
    print(f"[visual-planner] WARNING: {_CATALOG_PATH} not found — library visuals disabled in prompt")

# ---------------------------------------------------------------------------
# Pydantic models – mirror the Zod VisualSpecSchema in remotion/src/visualAdapter.ts
# ---------------------------------------------------------------------------

ProcessKind = Literal[
    "transfer", "sequence", "cycle", "mechanism",
    "structure", "contrast", "quantity", "relationships",
    "algorithm", "data-structure", "protocol", "architecture",
    "operations", "database", "code",
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
    "algorithm": "array",
    "data-structure": "array",
    "protocol": "exchange",
    "architecture": "architecture",
    "operations": "pipeline",
    "database": "table",
    "code": "code",
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


_LIBRARY_TYPES = frozenset([
    "array", "tree", "chain", "graph", "exchange", "code",
    "architecture", "balancer", "ring", "cache",
    "pipeline", "deploy",
    "table", "join", "indexscan", "replication", "sharding",
])


class _LibrarySpec(BaseModel):
    """Permissive pass-through for library visual types. Remotion's zod validates them."""
    type: str
    model_config = {"extra": "allow"}


_VISUAL_UNION = (
    _FlowSpec | _HubSpec | _BarsSpec | _SequenceSpec | _CycleSpec
    | _LayersSpec | _AnatomySpec | _ComparisonSpec | _SceneGraphSpec
    | _LibrarySpec
)


class _PlannerSceneOutput(BaseModel):
    concept: str
    processKind: ProcessKind
    visual: dict[str, Any]


# ---------------------------------------------------------------------------
# Gemini visual planner
# ---------------------------------------------------------------------------

_PLANNER_SYSTEM_BASE = """
You are an educational visual planner. Given a scene's narration, you classify it
and design one visual diagram for Remotion to render.

For EACH scene, return JSON with exactly these fields:
1. concept: the single idea this scene's narration teaches (one sentence).
2. processKind: one of transfer | sequence | cycle | mechanism | structure | contrast | quantity | relationships | algorithm | data-structure | protocol | architecture | operations | database | code
3. visual: a spec of the matching type.

Mapping (use the left side to pick the visual type):
  transfer       → flow
  sequence       → sequence
  cycle          → cycle
  mechanism      → layers
  structure      → anatomy
  contrast       → comparison
  quantity       → bars
  relationships  → scene-graph   (LAST RESORT — every node needs x/y)
  hub is also valid for one thing with several inputs or outputs.

processKind also accepts:
  "algorithm"      – a named algorithm on data (array, tree, chain, graph)
  "data-structure" – how a structure stores or changes data (array, tree, chain, graph, table)
  "protocol"       – parties exchanging messages in order (exchange)
  "architecture"   – how components are wired (architecture, balancer, ring, cache)
  "operations"     – shipping and running software (pipeline, deploy)
  "database"       – queries, indexes, replication, sharding (table, join, indexscan, replication, sharding)
  "code"           – what a snippet does (code)

Available library visuals (use EXACTLY these JSON shapes; the renderer validates them):
{catalog}

Rules:
- Never write algorithm steps or query results. Supply inputs only; the renderer computes the steps.
- Choose per scene from the concept. The video's overall topic is NOT a factor.
- Do not use the same visual type for consecutive scenes unless the concept is genuinely the same.
- Do NOT use the same visual type for consecutive scenes unless their processKind is genuinely the same.
- Labels: max 3 words, UPPERCASE for node labels. Footnote: one factual sentence.
- Only use facts from the narration. Never invent numbers.
- Use a library visual only when the narration is actually about that concept. Otherwise use flow, hub, bars or scene-graph.
- For narration explaining how a database index finds a target row without scanning every row, prefer the "indexscan" library visual. Use it only when that lookup-versus-scan concept is actually explained in the narration. Its values are illustrative row IDs, not factual measurements; choose 6-12 distinct integer IDs and make target one of those IDs.
- Use cycle only when the narration describes a genuinely repeating process;
  movement or changing positions alone does not establish a cycle.
- Use comparison only when the narration explicitly contrasts two things.
- Every scene needs a title (max 6 words).
- Icons must come from: sun, panel, cell, bolt, inverter, house, syringe, virus, immune, shield, antibody, rna, protein, gear, link, check, dot, heart, or be omitted.
- Colors must be one of: teal, gold, red, purple, white.
- code: put in `output` ONLY text the narration states. Never invent program output.

Type constraints — follow these exact JSON shapes:
- flow: {{"type":"flow","title":"...","nodes":[{{"label":"...","icon":"sun"}},{{"label":"...","icon":"panel"}}]}}
  Use 2-4 node objects, not strings.
- hub: {{"type":"hub","center":{{"label":"...","icon":"dot"}},"satellites":[{{"label":"..."}},{{"label":"..."}}]}}
  Use one center object and 2-6 satellite objects.
- cycle: {{"type":"cycle","title":"...","stages":[{{"label":"MORNING POSITION"}},{{"label":"MIDDAY POSITION"}},{{"label":"EVENING POSITION"}}]}}
  Every stage MUST be an object containing a label. Never return stages as strings.
- sequence: {{"type":"sequence","title":"...","steps":[{{"label":"STEP ONE","detail":"..."}},{{"label":"STEP TWO","detail":"..."}}]}}
  Every step MUST be an object. Use 2-5 steps.
- layers: {{"type":"layers","title":"...","layers":[{{"label":"TOP LAYER"}},{{"label":"BOTTOM LAYER"}}]}}
  Use 2-6 layer objects listed TOP TO BOTTOM. If carriers are used, fromLayer and toLayer are zero-based indexes.
- anatomy: {{"type":"anatomy","title":"...","subject":"block","parts":[{{"label":"PART ONE","note":"..."}},{{"label":"PART TWO","note":"..."}}]}}
  subject must be circle, capsule, block, or blob. Use 2-6 part objects.
- comparison: {{"type":"comparison","title":"...","left":{{"heading":"...","points":["..."]}},"right":{{"heading":"...","points":["..."]}}}}
  Each side needs a heading and 1-4 point strings.
- bars: {{"type":"bars","title":"...","bars":[{{"label":"...","value":10}},{{"label":"...","value":20}}]}}
  Use 2-6 bars. Each numeric value MUST exactly match a number explicitly stated in that scene's narration. Do not estimate, infer, invent, or use illustrative values. If the narration has no suitable explicit numbers, choose another visual type.
- scene-graph: LAST RESORT only. Shape:
  {{"type":"scene-graph","title":"...","nodes":[{{"id":"a","label":"A","x":200,"y":150}},{{"id":"b","label":"B","x":600,"y":150}}],"links":[{{"from":"a","to":"b","label":"..."}}]}}
  Every node needs a unique id, x from 0-1000, and y from 0-430. The links array is REQUIRED and must be present, even if empty. Every link's from and to must reference node ids.
- All nested nodes, stages, steps, layers, parts, bars, and links must be JSON objects with the required fields, not plain strings.
- Never use illustration. If no valid visual can be designed from the narration, return visual as null.
""".strip()

_PLANNER_SYSTEM = _PLANNER_SYSTEM_BASE.format(catalog=_PLANNER_CATALOG if _PLANNER_CATALOG else "(catalog not available)")


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
        f"Scene {s['scene_number']}:\n"
        f"Narration: {s['narration']}\n"
        f"Visual direction: {s.get('visual_description', 'Choose a visual based on the narration.')}"
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

                    # Bar values must be explicitly supported by this scene's narration.
                    if vtype == "bars":
                        narration = scenes[i].get("narration", "")
                        number_matches = re.findall(
                            r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?",
                            narration,
                        )
                        narration_numbers = {
                            float(number.rstrip("%").replace(",", ""))
                            for number in number_matches
                        }

                        bar_values = [bar.value for bar in validated.bars]

                        if not narration_numbers or any(
                            not any(abs(value - spoken) < 1e-9 for spoken in narration_numbers)
                            for value in bar_values
                        ):
                            raise ValueError(
                                "Bar values must match numbers explicitly stated "
                                "in the scene narration."
                            )

                    validated_visual = validated.model_dump(
                        exclude_none=True,
                        by_alias=True,
                    )

                elif vtype in _LIBRARY_TYPES:
                    # Library visuals have their own schemas in Remotion.
                    # Preserve their complete specs for the Remotion adapter.
                    validated = _LibrarySpec.model_validate(visual_dict)
                    validated_visual = validated.model_dump(
                        exclude_none=True,
                        by_alias=True,
                    )
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
    """Split at sentence boundaries whenever a sentence is reasonably sized."""
    sentences = re.split(r"(?<=[.!?])\s+", script.strip())
    segments = []

    for sentence in sentences:
        words = sentence.split()

        if not words:
            continue

        # Preserve complete sentences up to 40 words to avoid broken narration.
        if len(words) <= max(MAX_WORDS_PER_SCENE, 40):
            segments.append(" ".join(words))
            continue

        # Only unusually long sentences need chunking.
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
    if re.search(r"\bheart\b|\bcardiac\b", topic_text):
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
        # A closing summary should communicate the overall application.
        # A tracking detail must not take over the entire scene.
        if re.search(
            r"whether mounted|these systems turn|power our lives|"
            r"clean, reliable energy|overall|in summary|to sum up",
            narration,
            re.IGNORECASE,
        ):
            focus = (
                "the overall solar-power application, showing sunlight "
                "being used to provide useful electricity and power "
                "everyday life; treat tracking as a secondary detail"
            )
        elif re.search(
            r"track(?:ing|er|s)?|follow(?:ing|s)? the sun|sun's path|sun’s path",
            narration,
            re.IGNORECASE,
        ):
            focus = (
                "solar tracking technology following the sun's path "
                "compared with fixed-mounted panels, without inventing "
                "quantities or guaranteed performance gains"
            )
        elif re.search(
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



def _physics_visual_description(topic: str, narration: str) -> str:
    """Describe the physics concept actually discussed in this scene."""
    text = narration.casefold()

    if re.search(
        r"five connected ideas|five physics ideas|connecting .* ideas|"
        r"together, (?:these concepts|these ideas|they link)",
        text,
    ):
        focus = "an overview connecting forces, motion, and energy"
    elif re.search(
        r"projectile|trajectory|launched|thrown|"
        r"horizontal.*vertical|vertical.*horizontal",
        text,
    ):
        focus = "projectile trajectory with horizontal and vertical motion"
    elif re.search(r"free fall|falling object", text):
        focus = "an object accelerating under gravity during free fall"
    elif re.search(
        r"potential energy|gravitational potential|mgh|stored energy|"
        r"height can represent",
        text,
    ):
        focus = "gravitational potential energy and the role of height"
    elif re.search(r"kinematics|velocity|displacement|speed|position", text):
        focus = "kinematics quantities describing position and motion"
    elif re.search(r"force|newton|free.body|friction|tension|acceleration", text):
        focus = "the forces and motion relationships explained"
    elif re.search(r"energy|kinetic|work done|power", text):
        focus = "the energy transfers or transformations explained"
    elif re.search(r"projectile|trajectory", topic.casefold()):
        # Retain a useful fallback for vague projectile-motion narration.
        focus = "projectile trajectory and the role of gravity"
    else:
        focus = "the physical quantities and relationships explained"

    return (
        f"Physics illustration focused on {focus}. "
        "Show only quantities, vectors, trajectories, and relationships "
        "supported by the topic and narration. "
        f"Scene narration: {narration} "
        "Avoid invented numerical values or unsupported assumptions."
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



def _physics_visual(topic: str, narration: str) -> dict | None:
    """Build a concept-specific physics diagram from this scene's narration."""
    text = narration.casefold()
    focused_topic = topic.casefold().strip()

    def graph(title, nodes, links, footnote):
        # Reveal concepts first, then explain their relationships.
        node_step = 0.24
        link_step = 0.22
        first_node_at = 0.2

        staged_nodes = [
            {**item, "appearAt": first_node_at + index * node_step}
            for index, item in enumerate(nodes)
        ]

        first_link_at = first_node_at + len(staged_nodes) * node_step

        staged_links = [
            {**item, "appearAt": first_link_at + index * link_step}
            for index, item in enumerate(links)
        ]

        return {
            "type": "scene-graph",
            "title": title,
            "nodes": staged_nodes,
            "links": staged_links,
            "footnote": footnote,
        }

    def node(node_id, label, x, y, color):
        return {
            "id": node_id,
            "label": label,
            "x": x,
            "y": y,
            "size": 38,
            "color": color,
            "appearAt": 0.2,
        }

    def link(source, target, label, color="#4FD1C5"):
        return {
            "from": source,
            "to": target,
            "label": label,
            "color": color,
            "style": "solid",
            "appearAt": 0.4,
        }

    # Overview scenes should connect the ideas instead of showing one concept.
    if re.search(
        r"\bfive connected ideas\b|\bfive physics ideas\b|"
        r"\boverview of physics\b|\bthese concepts connect\b|"
        r"\btogether, these ideas connect\b",
        text,
    ):
        nodes = [
            node("forces", "FORCES", 160, 105, "#4FD1C5"),
            node("motion", "MOTION", 500, 105, "#F2B84B"),
            node("gravity", "GRAVITY", 830, 105, "#E87979"),
            node("trajectory", "TRAJECTORY", 300, 310, "#5B9BFF"),
            node("energy", "POTENTIAL ENERGY", 700, 310, "#A78BFA"),
        ]
        return graph(
            "Five Connected Physics Ideas",
            nodes,
            [
                link("forces", "motion", "CHANGE MOTION"),
                link("gravity", "trajectory", "SHAPES PATH"),
                link("gravity", "energy", "RELATES TO HEIGHT"),
                link("motion", "trajectory", "DESCRIBES"),
            ],
            "Conceptual connections; not a numerical model.",
        )

    # Projectile motion: distinguish horizontal and vertical motion.
    if re.search(
        r"\bprojectile\b|\btrajectory\b|\bhorizontal and vertical\b|"
        r"\bvertical and horizontal\b|\bthrown object\b|"
        r"\bobject is launched\b|\bcurved path\b",
        text,
    ):
        return graph(
            "Projectile Motion",
            [
                node("launch", "LAUNCH", 140, 210, "#F2B84B"),
                node("horizontal", "HORIZONTAL MOTION", 440, 100, "#4FD1C5"),
                node("vertical", "VERTICAL MOTION", 440, 320, "#E87979"),
                node("gravity", "GRAVITY", 640, 400, "#F2B84B"),
                node("path", "CURVED TRAJECTORY", 850, 210, "#5B9BFF"),
            ],
            [
                link("launch", "horizontal", "HORIZONTAL COMPONENT"),
                link("launch", "vertical", "VERTICAL COMPONENT"),
                link("gravity", "vertical", "ACCELERATES"),
                link("horizontal", "path", "COMBINES"),
                link("vertical", "path", "COMBINES"),
            ],
            "Idealized trajectory; no launch speed or angle assumed.",
        )

    # Free fall: gravity changes downward velocity.
    if re.search(
        r"\bfree fall\b|\bfalling object\b|\bdropped object\b|"
        r"\bfalls freely\b|\bfalls under gravity\b",
        text,
    ):
        return graph(
            "Free Fall",
            [
                node("object", "FALLING OBJECT", 180, 110, "#4FD1C5"),
                node("gravity", "GRAVITY", 500, 110, "#F2B84B"),
                node("acceleration", "DOWNWARD ACCELERATION", 500, 320, "#E87979"),
                node("velocity", "VELOCITY", 820, 320, "#5B9BFF"),
            ],
            [
                link("gravity", "acceleration", "CAUSES"),
                link("acceleration", "velocity", "CHANGES"),
                link("object", "velocity", "MOTION"),
            ],
            "Air resistance is neglected in the ideal free-fall model.",
        )

    # Gravitational potential energy: make height and mass explicit.
    if re.search(
        r"\bpotential energy\b|\bgravitational potential\b|\bmgh\b|"
        r"\bstored energy\b",
        text,
    ):
        return graph(
            "Gravitational Potential Energy",
            [
                node("height", "HEIGHT ABOVE REFERENCE", 180, 110, "#4FD1C5"),
                node("mass", "MASS", 180, 320, "#F2B84B"),
                node("gravity", "GRAVITY", 500, 320, "#5B9BFF"),
                node("energy", "POTENTIAL ENERGY", 820, 210, "#A78BFA"),
            ],
            [
                link("height", "energy", "AFFECTS"),
                link("mass", "energy", "AFFECTS"),
                link("gravity", "energy", "AFFECTS"),
            ],
            "Gravitational potential energy depends on mass, gravity, and height.",
        )

    # Newton's second law: force, mass, and acceleration.
    if re.search(
        r"\bnewton(?:'s)? second law\b|\bnet force\b|"
        r"\bforce.*\bmass\b.*\bacceleration\b|"
        r"\bacceleration.*\bnet force\b|"
        r"\bforces come first\b",
        text,
    ):
        return graph(
            "Newton's Second Law",
            [
                node("force", "NET FORCE", 180, 110, "#4FD1C5"),
                node("mass", "MASS", 180, 320, "#F2B84B"),
                node("acceleration", "ACCELERATION", 820, 210, "#A78BFA"),
            ],
            [
                link("force", "acceleration", "PRODUCES"),
                link("mass", "acceleration", "AFFECTS"),
            ],
            "For a fixed mass, greater net force produces greater acceleration.",
        )

    # Kinematics: represent change in position without inventing values.
    if re.search(
        r"\bkinematics\b|\bdisplacement\b|\bvelocity\b|"
        r"\bposition over time\b|\bchange in position\b|"
        r"\bnext, describe motion\b",
        text,
    ):
        return graph(
            "Describing Motion",
            [
                node("initial", "INITIAL POSITION", 160, 210, "#4FD1C5"),
                node("final", "FINAL POSITION", 500, 100, "#F2B84B"),
                node("time", "ELAPSED TIME", 500, 320, "#5B9BFF"),
                node("displacement", "DISPLACEMENT", 830, 210, "#A78BFA"),
            ],
            [
                link("initial", "displacement", "COMPARES WITH"),
                link("final", "displacement", "CHANGE IN POSITION"),
                link("time", "displacement", "OVER A TIME INTERVAL"),
            ],
            "Conceptual diagram; no numerical measurements assumed.",
        )

    # A single-concept topic may be vague in one scene. Do not use this
    # fallback for a broad topic that lists several different concepts.
    if re.fullmatch(r"(?:how does |how to understand )?projectile motion", focused_topic):
        return graph(
            "Projectile Motion",
            [
                node("launch", "LAUNCH", 160, 210, "#F2B84B"),
                node("gravity", "GRAVITY", 500, 100, "#E87979"),
                node("path", "CURVED PATH", 820, 210, "#5B9BFF"),
            ],
            [
                link("launch", "path", "STARTS MOTION"),
                link("gravity", "path", "BENDS TRAJECTORY"),
            ],
            "Idealized projectile motion.",
        )

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


def _deterministic_library_visual(
    topic: str,
    narration: str,
) -> dict[str, Any] | None:
    """Choose a registered Remotion visual from explicit CS scene content.

    Example values in these specs are illustrative animation data, not facts
    inferred from the narration. Specialised science visuals are left to the
    existing visual resolver.
    """
    topic_text = topic.lower()
    sentence = narration.lower()

    # Preserve the existing specialised topic visuals.
    specialised_topics = (
        "solar", "photovoltaic", "vaccine", "immun",
        "heart", "blood circulation", "water cycle",
        "projectile", "physics",
    )
    if any(term in topic_text for term in specialised_topics):
        return None

    # More specific database concepts must win over generic table/code matches.
    if "index" in sentence and any(
        term in sentence for term in ("database", "query", "row", "scan")
    ):
        return {
            "type": "indexscan",
            "title": "Finding a row with an index",
            "values": [42, 7, 19, 88, 3, 56, 71, 25],
            "target": 71,
        }

    if "join" in sentence and any(
        term in sentence for term in ("sql", "table", "database", "rows")
    ):
        return {
            "type": "join",
            "title": "Combining related tables",
            "left": {
                "name": "users",
                "columns": ["id", "name"],
                "rows": [[1, "Ana"], [2, "Ben"], [3, "Cara"]],
            },
            "right": {
                "name": "orders",
                "columns": ["user_id", "item"],
                "rows": [[1, "Book"], [1, "Pen"], [3, "Bag"]],
            },
            "on": {"left": "id", "right": "user_id"},
            "joinType": "left",
        }

    if any(term in sentence for term in ("replication", "replica", "replicas")):
        return {
            "type": "replication",
            "title": "Database replication",
            "replicas": 2,
            "mode": "async",
            "writes": 3,
            "failover": True,
        }

    if any(term in sentence for term in ("sharding", "shard key", "shards")):
        return {
            "type": "sharding",
            "title": "Splitting data across shards",
            "shards": 3,
            "keys": ["ana", "ben", "cara", "dan", "eli", "fay"],
            "strategy": "hash",
        }

    if any(term in sentence for term in ("lru cache", "cache hit", "cache miss", "cache eviction")):
        return {
            "type": "cache",
            "title": "How a cache works",
            "capacity": 3,
            "policy": "lru",
            "accesses": ["A", "B", "C", "A", "D", "B"],
        }

    if "binary search" in sentence:
        return {
            "type": "array",
            "title": "Binary search",
            "values": [3, 8, 12, 19, 25, 31, 42],
            "algorithm": "binary-search",
            "target": 25,
        }

    if any(term in sentence for term in ("bubble sort", "sorting algorithm", "sorts an array")):
        return {
            "type": "array",
            "title": "Bubble sort",
            "values": [5, 2, 9, 1, 7, 3],
            "algorithm": "bubble-sort",
            "footnote": "Large values bubble toward the end",
        }

    if "linear search" in sentence:
        return {
            "type": "array",
            "title": "Linear search",
            "values": [5, 2, 9, 1, 7, 3],
            "algorithm": "linear-search",
            "target": 7,
        }

    if any(term in sentence for term in ("binary search tree", "bst", "tree traversal", "parent node", "child node")):
        return {
            "type": "tree",
            "title": "Traversing a binary tree",
            "values": [8, 3, 10, 1, 6, 14, 4],
            "algorithm": "inorder",
        }

    if any(term in sentence for term in ("stack", "queue", "linked list", "push", "pop", "enqueue", "dequeue")):
        kind = "queue" if any(
            term in sentence for term in ("queue", "enqueue", "dequeue")
        ) else "stack"
        return {
            "type": "chain",
            "title": "Working with a " + kind,
            "kind": kind,
            "values": [4, 7, 2] if kind == "stack" else [1, 2, 3],
            "ops": (
                [{"op": "pop"}, {"op": "push", "value": 9}]
                if kind == "stack"
                else [{"op": "dequeue"}, {"op": "enqueue", "value": 4}]
            ),
        }

    if any(term in sentence for term in ("breadth-first search", "bfs", "depth-first search", "dfs", "graph traversal")):
        algorithm = "bfs" if any(
            term in sentence for term in ("breadth-first search", "bfs")
        ) else "dfs"
        return {
            "type": "graph",
            "title": "Graph traversal",
            "nodes": ["A", "B", "C", "D", "E", "F"],
            "edges": [
                {"from": "A", "to": "B"},
                {"from": "A", "to": "C"},
                {"from": "B", "to": "D"},
                {"from": "B", "to": "E"},
                {"from": "C", "to": "F"},
            ],
            "algorithm": algorithm,
            "start": "A",
        }

    if any(term in sentence for term in ("http request", "api request", "request and response", "client-server", "rest api")):
        return {
            "type": "exchange",
            "title": "A client-server request",
            "actors": ["Browser", "Server", "Database"],
            "messages": [
                {"from": "Browser", "to": "Server", "label": "Request"},
                {"from": "Server", "to": "Database", "label": "Query"},
                {"from": "Database", "to": "Server", "label": "Result", "reply": True},
                {"from": "Server", "to": "Browser", "label": "Response", "reply": True},
            ],
        }

    if any(term in sentence for term in ("load balancer", "load balancing")):
        return {
            "type": "balancer",
            "title": "Distributing incoming traffic",
        }

    if any(term in sentence for term in ("consistent hashing", "hash ring")):
        return {
            "type": "ring",
            "title": "Consistent hashing",
        }

    if any(term in sentence for term in ("deployment pipeline", "ci/cd", "continuous integration", "continuous delivery")):
        return {
            "type": "pipeline",
            "title": "A CI/CD pipeline",
            "stages": [
                {"name": "Build", "jobs": ["Compile"]},
                {"name": "Test", "jobs": ["Unit tests", "Integration tests"]},
                {"name": "Deploy", "jobs": ["Release"]},
            ],
        }

    if any(term in sentence for term in ("canary release", "blue-green deployment", "deployment strategy")):
        return {
            "type": "deploy",
            "title": "A staged deployment",
            "strategy": "canary",
            "instances": 4,
            "from": "v1",
            "to": "v2",
        }

    if any(term in sentence for term in ("system architecture", "software architecture", "three-tier architecture")):
        return {
            "type": "architecture",
            "title": "A web application architecture",
            "nodes": [
                {"id": "client", "label": "Client", "kind": "client"},
                {"id": "server", "label": "Application server", "kind": "server"},
                {"id": "database", "label": "Database", "kind": "database"},
            ],
            "links": [
                {"from": "client", "to": "server"},
                {"from": "server", "to": "database"},
            ],
            "path": ["client", "server", "database"],
        }

    if any(term in sentence for term in ("python code", "for loop", "variable", "function definition", "execute this code")):
        return {
            "type": "code",
            "title": "A small Python program",
            "language": "python",
            "lines": [
                "total = 0",
                "for n in [1, 2, 3]:",
                "    total += n",
                "print(total)",
            ],
            "steps": [
                {"line": 1, "note": "Start the total at zero"},
                {"line": 2, "note": "Visit each number"},
                {"line": 3, "note": "Add the current number"},
                {"line": 4, "note": "Display the total", "output": "6"},
            ],
        }

    if any(term in sentence for term in ("sql table", "database table", "rows and columns", "select query")):
        return {
            "type": "table",
            "title": "Selecting rows from a table",
            "name": "users",
            "columns": ["id", "name", "age", "city"],
            "rows": [
                [1, "Ana", 31, "Lima"],
                [2, "Ben", 24, "Nairobi"],
                [3, "Cara", 29, "Accra"],
            ],
            "query": {
                "kind": "select",
                "columns": ["name", "age"],
                "where": {"column": "age", "op": ">", "value": 27},
            },
        }

    if any(term in sentence for term in ("array", "list of elements", "element at index")):
        return {
            "type": "array",
            "title": "An array of values",
            "values": [5, 2, 9, 1, 7, 3],
            "algorithm": "bubble-sort",
        }

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
            "visual_description": (
                _physics_visual_description(topic, narration)
                if state.get("category", "cs") == "physics"
                else _visual_description(topic, narration)
            ),
            "duration_seconds": duration,
        }

        visual: dict[str, Any] | None = None

        if use_semantic_graph:
            visual = _semantic_visual(narration)

        # Prefer a topic-relevant Remotion library visual for CS scenes.
        # Keep the existing specialised physics/science paths untouched.
        if visual is None and state.get("category", "cs") == "cs":
            visual = _deterministic_library_visual(topic, narration)

        # Give physics scenes a concept-specific diagram before the
        # generic relationship parser gets a chance to create a weak match.
        if visual is None and state.get("category", "cs") == "physics":
            visual = _physics_visual(topic, narration)

        # Preserve the existing relationship diagram as the next fallback.
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
