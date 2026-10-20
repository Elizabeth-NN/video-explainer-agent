from app.graph.scene_planner import scene_planner_node
from app.graph.workflow import build_graph


def test_scene_planner_creates_structured_scenes():
    state = {
        "topic": "How vaccines work",
        "script": (
            "Vaccines help the immune system recognize a threat. "
            "This can help the body respond in the future."
        ),
        "approved": True,
    }

    result = scene_planner_node(state)
    scenes = result["scenes"]

    assert len(scenes) == 2
    assert scenes[0]["scene_number"] == 1
    assert scenes[0]["narration"] == (
        "Vaccines help the immune system recognize a threat."
    )
    assert scenes[0]["visual_description"]
    assert scenes[0]["duration_seconds"] >= 2
    assert scenes[1]["scene_number"] == 2


def test_physics_category_uses_physics_specific_visual_description():
    state = {
        "topic": "Projectile motion",
        "script": "The object moves through the air along a curved path.",
        "approved": True,
        "category": "physics",
    }

    physics_scene = scene_planner_node(state)["scenes"][0]
    physics_description = physics_scene["visual_description"].lower()

    assert "projectile trajectory" in physics_description
    assert "gravity" in physics_description
    assert "narration" in physics_description

    # The default CS path must not infer physics details that were not stated.
    cs_state = {**state, "category": "cs"}
    cs_scene = scene_planner_node(cs_state)["scenes"][0]
    assert "gravity" not in cs_scene["visual_description"].lower()


def test_physics_scenes_get_concept_specific_visuals():
    from app.graph.scene_planner import scene_planner_node

    cases = [
        (
            "Newton's second law relates net force, mass, and acceleration.",
            "Newton's Second Law",
            {"NET FORCE", "MASS", "ACCELERATION"},
        ),
        (
            "Kinematics describes displacement and velocity over time.",
            "Describing Motion",
            {"INITIAL POSITION", "FINAL POSITION", "DISPLACEMENT"},
        ),
        (
            "In free fall, gravity accelerates a falling object downward.",
            "Free Fall",
            {"FALLING OBJECT", "GRAVITY", "DOWNWARD ACCELERATION"},
        ),
        (
            "A projectile follows a curved trajectory with horizontal and vertical motion.",
            "Projectile Motion",
            {"LAUNCH", "HORIZONTAL MOTION", "VERTICAL MOTION", "CURVED TRAJECTORY"},
        ),
        (
            "Gravitational potential energy depends on mass, gravity, and height.",
            "Gravitational Potential Energy",
            {"HEIGHT ABOVE REFERENCE", "MASS", "GRAVITY", "POTENTIAL ENERGY"},
        ),
    ]

    for narration, expected_title, expected_labels in cases:
        scene = scene_planner_node({
            "topic": "Physics fundamentals",
            "category": "physics",
            "script": narration,
            "approved": True,
        })["scenes"][0]

        visual = scene["visual"]
        assert visual["type"] == "scene-graph"
        assert visual["title"] == expected_title
        labels = {node["label"] for node in visual["nodes"]}
        assert expected_labels <= labels
        assert visual["links"]


def test_physics_overview_gets_a_connected_concept_diagram():
    scene = scene_planner_node({
        "topic": "Physics fundamentals: Newton's second law, kinematics, "
                 "free fall, projectile motion, and potential energy",
        "category": "physics",
        "script": "Imagine five connected ideas that explain forces, motion, and energy.",
        "approved": True,
    })["scenes"][0]

    visual = scene["visual"]
    assert visual["type"] == "scene-graph"
    assert visual["title"] == "Five Connected Physics Ideas"
    assert len(visual["nodes"]) == 5


def test_scene_planner_does_not_plan_unapproved_script():
    result = scene_planner_node(
        {
            "topic": "Test topic",
            "script": "A script that has not been approved.",
            "approved": False,
        }
    )

    assert result["scenes"] == []


def test_scene_planner_rejects_empty_approved_script():
    try:
        scene_planner_node(
            {"topic": "Test topic", "script": " ", "approved": True}
        )
    except ValueError as exc:
        assert "approved script" in str(exc)
    else:
        raise AssertionError("Expected empty approved script to be rejected.")


def test_approved_graph_output_contains_scenes():
    from unittest.mock import patch

    state = {
        "topic": "How vaccines work",
        "research_notes": ["Vaccines help prepare the immune system."],
        "research_sources": [
            {
                "title": "Vaccine overview",
                "url": "https://example.com/vaccines",
                "summary": "Vaccines help the immune system recognize pathogens.",
            }
        ],
        "research_quality": "limited",
        "script": "",
        "critique": "",
        "approved": False,
        "revision_count": 0,
    }

    with (
        patch(
            "app.graph.workflow.research_node",
            return_value={
                "research_quality": "limited",
                "research_notes": ["Vaccines help prepare the immune system."],
                "research_sources": state["research_sources"],
            },
        ),
        patch(
            "app.graph.workflow.scriptwriter_node",
            return_value={
                "script": (
                    "Vaccines help the immune system recognize a threat. "
                    "This prepares the body to respond."
                )
            },
        ),
        patch(
            "app.graph.workflow.critic_node",
            return_value={"approved": True, "critique": "Approved."},
        ),
    ):
        result = build_graph().invoke(state)

    assert result["approved"] is True
    assert len(result["scenes"]) == 2
    assert result["scenes"][0]["narration"].startswith("Vaccines help")



def test_scene_visual_descriptions_follow_narrated_concepts():
    solar = scene_planner_node(
        {
            "topic": "How solar panels work",
            "script": "A battery stores electricity for later use.",
            "approved": True,
        }
    )["scenes"][0]

    assert "battery" in solar["visual_description"].lower()
    assert "narration" in solar["visual_description"].lower()

    vaccine = scene_planner_node(
        {
            "topic": "How vaccines work",
            "script": "This can help the body respond during future exposure.",
            "approved": True,
        }
    )["scenes"][0]

    assert "immune memory" in vaccine["visual_description"].lower()


def test_general_scene_description_does_not_assume_a_specific_subject():
    scene = scene_planner_node(
        {
            "topic": "How rain forms",
            "script": "Water vapor cools and forms tiny droplets.",
            "approved": True,
        }
    )["scenes"][0]

    description = scene["visual_description"].lower()
    assert "water vapor cools" in description
    assert "solar panel" not in description
    assert "vaccine" not in description


def test_generic_visual_plan_uses_explicit_inflation_relationship():
    scene = scene_planner_node(
        {
            "topic": "Inflation",
            "script": "Inflation increases the general price level.",
            "approved": True,
        }
    )["scenes"][0]

    assert scene["visual"]["type"] == "scene-graph"
    nodes = scene["visual"]["nodes"]
    labels = [node["label"] for node in nodes]
    assert labels == ["INFLATION", "GENERAL PRICE LEVEL"]
    assert [node["id"] for node in nodes] == ["source", "outcome"]
    assert nodes[0]["x"] < nodes[1]["x"]
    assert scene["visual"]["links"][0]["from"] == "source"
    assert scene["visual"]["links"][0]["to"] == "outcome"
    assert scene["visual"]["links"][0]["label"] == "INCREASES"


def test_generic_visual_plan_handles_water_cycle_relationship():
    scene = scene_planner_node(
        {
            "topic": "How rain forms",
            "script": "Water vapor cools and forms tiny droplets.",
            "approved": True,
        }
    )["scenes"][0]

    assert scene["visual"]["type"] == "scene-graph"
    nodes = scene["visual"]["nodes"]
    labels = [node["label"] for node in nodes]
    assert labels == ["WATER VAPOR", "TINY DROPLETS"]
    assert scene["visual"]["links"][0]["label"] == "FORMS"
    assert all("x" in node and "y" in node for node in nodes)



def test_water_cycle_evaporation_wording_creates_scene_graph():
    scene = scene_planner_node(
        {
            "topic": "The Water Cycle",
            "script": (
                "Energy from the Sun warms water at Earth's surface, "
                "allowing some of it to evaporate and enter the atmosphere "
                "as water vapour."
            ),
            "approved": True,
        }
    )["scenes"][0]

    assert scene["visual"]["type"] == "scene-graph"
    labels = [node["label"] for node in scene["visual"]["nodes"]]
    assert labels == ["WATER", "WATER VAPOUR"]
    assert scene["visual"]["links"][0]["label"] == "EVAPORATES INTO"


def test_water_cycle_precipitation_wording_creates_scene_graph():
    scene = scene_planner_node(
        {
            "topic": "The Water Cycle",
            "script": (
                "Water can fall back to Earth's surface as precipitation, "
                "such as rain or snow."
            ),
            "approved": True,
        }
    )["scenes"][0]

    assert scene["visual"]["type"] == "scene-graph"
    labels = [node["label"] for node in scene["visual"]["nodes"]]
    assert labels == ["WATER", "PRECIPITATION"]
    assert scene["visual"]["links"][0]["label"] == "FALLS AS"


def test_water_cycle_condensation_wording_creates_scene_graph():
    scene = scene_planner_node(
        {
            "topic": "The Water Cycle",
            "script": (
                "As the vapour cools, it can condense into tiny water "
                "droplets that form clouds."
            ),
            "approved": True,
        }
    )["scenes"][0]

    assert scene["visual"]["type"] == "scene-graph"
    labels = [node["label"] for node in scene["visual"]["nodes"]]
    assert labels == ["VAPOUR", "TINY WATER DROPLETS"]
    assert scene["visual"]["links"][0]["label"] == "CONDENSES INTO"


def test_generic_visual_plan_does_not_invent_a_relationship():
    scene = scene_planner_node(
        {
            "topic": "A broad introduction",
            "script": "This topic has several important parts.",
            "approved": True,
        }
    )["scenes"][0]

    assert "visual" not in scene


def test_heart_scene_visual_descriptions_follow_blood_flow_narration():
    result = scene_planner_node(
        {
            "topic": "How the human heart pumps blood",
            "script": (
                "Blood returning from the body enters the right side "
                "through the superior and inferior venae cavae. "
                "The right side pumps blood to the lungs through the "
                "pulmonary artery. The left side receives blood returning "
                "from the lungs."
            ),
            "approved": True,
        }
    )

    descriptions = [
        scene["visual_description"].lower()
        for scene in result["scenes"]
    ]

    assert "illustrate blood returning from the body" in descriptions[0]
    assert "sending blood toward the lungs through the pulmonary artery" in descriptions[1]
    assert "blood returning from the lungs and entering the left side" in descriptions[2]
    assert all("scene narration:" in item for item in descriptions)
    assert all("illustrate the specific idea in this scene" not in item for item in descriptions)


def test_solar_scene_mentioning_the_heart_does_not_trigger_heart_description():
    scene = scene_planner_node(
        {
            "topic": "How solar panels turn sunlight into electricity",
            "script": (
                "At the heart of these panels are photovoltaic cells."
            ),
            "approved": True,
        }
    )["scenes"][0]

    description = scene["visual_description"].lower()

    assert "photovoltaic" in description or "solar" in description
    assert "blood returning from the body" not in description
    assert "pulmonary artery" not in description


def test_water_cycle_sunlight_does_not_trigger_solar_description():
    scene = scene_planner_node(
        {
            "topic": "The Water Cycle",
            "script": "Sunlight drives evaporation.",
            "approved": True,
        }
    )["scenes"][0]

    description = scene["visual_description"].lower()
    assert "water-cycle" in description
    assert "evaporation" in description
    assert "solar panel" not in description


def test_water_cycle_condensation_creates_scene_graph():
    scene = scene_planner_node(
        {
            "topic": "The Water Cycle",
            "script": (
                "Water vapour cools and condenses into clouds, "
                "then falls as precipitation."
            ),
            "approved": True,
        }
    )["scenes"][0]

    assert scene["visual"]["type"] == "scene-graph"
    nodes = scene["visual"]["nodes"]
    assert [node["label"] for node in nodes] == ["WATER VAPOUR", "CLOUDS"]
    assert scene["visual"]["links"][0]["label"] == "CONDENSES INTO"
    assert "water-cycle" in scene["visual_description"].lower()


def test_water_cycle_evaporation_creates_scene_graph():
    scene = scene_planner_node(
        {
            "topic": "The Water Cycle",
            "script": "Sunlight heats water, causing evaporation.",
            "approved": True,
        }
    )["scenes"][0]

    assert scene["visual"]["type"] == "scene-graph"
    nodes = scene["visual"]["nodes"]
    assert [node["label"] for node in nodes] == [
        "SUNLIGHT HEATS WATER",
        "EVAPORATION",
    ]
    assert scene["visual"]["links"][0]["label"] == "CAUSES"


def test_water_cycle_clouds_releasing_precipitation_creates_scene_graph():
    scene = scene_planner_node(
        {
            "topic": "The Water Cycle",
            "script": "Clouds release precipitation, and water returns to rivers.",
            "approved": True,
        }
    )["scenes"][0]

    assert scene["visual"]["type"] == "scene-graph"
    nodes = scene["visual"]["nodes"]
    assert [node["label"] for node in nodes] == [
        "CLOUDS",
        "PRECIPITATION",
    ]
    assert scene["visual"]["links"][0]["label"] == "RELEASE"


def test_semantic_graph_pipeline_is_opt_in():
    from unittest.mock import patch

    state = {
        "topic": "Energy",
        "script": "Energy causes temperature to increase.",
        "approved": True,
    }

    with patch(
        "app.graph.scene_planner.extract_semantic_graph"
    ) as extractor:
        result = scene_planner_node(state)

    extractor.assert_not_called()
    assert result["scenes"][0]["visual"]["type"] == "scene-graph"


def test_semantic_graph_pipeline_creates_remotion_visual():
    from unittest.mock import patch

    graph = {
        "schema_version": 1,
        "nodes": [
            {"id": "energy", "label": "Energy"},
            {"id": "temperature", "label": "Temperature"},
        ],
        "edges": [
            {
                "source": "energy",
                "target": "temperature",
                "relationship": "increases",
            }
        ],
    }
    state = {
        "topic": "Energy",
        "script": "Energy changes temperature.",
        "approved": True,
    }

    with patch(
        "app.graph.scene_planner.extract_semantic_graph",
        return_value=graph,
    ):
        result = scene_planner_node(state, use_semantic_graph=True)

    visual = result["scenes"][0]["visual"]
    assert visual["type"] == "scene-graph"
    assert {node["id"] for node in visual["nodes"]} == {
        "energy",
        "temperature",
    }
    assert visual["links"][0]["from"] == "energy"
    assert visual["links"][0]["to"] == "temperature"
    assert visual["links"][0]["label"] == "INCREASES"


def test_semantic_graph_failure_uses_existing_visual_fallback():
    from unittest.mock import patch

    state = {
        "topic": "Energy",
        "script": "Heat causes water to evaporate.",
        "approved": True,
    }

    with patch(
        "app.graph.scene_planner.extract_semantic_graph",
        return_value=None,
    ):
        result = scene_planner_node(state, use_semantic_graph=True)

    # The deterministic planner still recognises this relationship.
    assert result["scenes"][0]["visual"]["type"] == "scene-graph"

def test_gemini_planner_rejects_bar_values_not_in_narration(monkeypatch):
    import json
    from unittest.mock import patch

    from app.graph.scene_planner import _call_gemini_planner

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    response_data = [
        {
            "concept": "Electricity generation",
            "processKind": "quantity",
            "visual": {
                "type": "bars",
                "title": "DC GENERATION",
                "bars": [
                    {"label": "ELECTRON FLOW", "value": 80, "color": "teal"},
                    {"label": "DC OUTPUT", "value": 95, "color": "gold"},
                ],
            },
        }
    ]

    with (
        patch("google.genai.Client") as client_class,
        patch("google.genai.types.GenerateContentConfig"),
    ):
        client = client_class.return_value
        client.models.generate_content.return_value.text = json.dumps(
            response_data
        )

        result = _call_gemini_planner(
            [
                {
                    "scene_number": 1,
                    "narration": (
                        "This movement creates direct current electricity."
                    ),
                }
            ],
            "How solar panels work",
        )

    assert result[0] is not None
    assert result[0]["visual"] is None

def test_gemini_planner_accepts_bar_values_stated_in_narration(monkeypatch):
    import json
    from unittest.mock import patch

    from app.graph.scene_planner import _call_gemini_planner

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    response_data = [
        {
            "concept": "Comparing stated quantities",
            "processKind": "quantity",
            "visual": {
                "type": "bars",
                "title": "STATED VALUES",
                "bars": [
                    {"label": "FIRST VALUE", "value": 80, "color": "teal"},
                    {"label": "SECOND VALUE", "value": 95, "color": "gold"},
                ],
            },
        }
    ]

    with (
        patch("google.genai.Client") as client_class,
        patch("google.genai.types.GenerateContentConfig"),
    ):
        client = client_class.return_value
        client.models.generate_content.return_value.text = json.dumps(
            response_data
        )

        result = _call_gemini_planner(
            [
                {
                    "scene_number": 1,
                    "narration": (
                        "The first value is 80 and the second value is 95."
                    ),
                }
            ],
            "Comparing two values",
        )

    assert result[0] is not None
    assert result[0]["visual"]["type"] == "bars"


def test_gemini_planner_rejects_cycle_stages_returned_as_strings(monkeypatch):
    import json
    from unittest.mock import patch

    from app.graph.scene_planner import _call_gemini_planner

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    response_data = [
        {
            "concept": "Sun tracking",
            "processKind": "cycle",
            "visual": {
                "type": "cycle",
                "title": "TRACKING THE SUN",
                "stages": [
                    "MORNING POSITION",
                    "MIDDAY POSITION",
                    "EVENING POSITION",
                ],
            },
        }
    ]

    with (
        patch("google.genai.Client") as client_class,
        patch("google.genai.types.GenerateContentConfig"),
    ):
        client = client_class.return_value
        client.models.generate_content.return_value.text = json.dumps(
            response_data
        )

        result = _call_gemini_planner(
            [
                {
                    "scene_number": 1,
                    "narration": (
                        "Tracking technology follows the sun across the sky."
                    ),
                }
            ],
            "How solar panels work",
        )

    assert result[0] is not None
    assert result[0]["concept"] == "Sun tracking"
    assert result[0]["visual"] is None


def test_gemini_planner_rejects_scene_graph_missing_links(monkeypatch):
    import json
    from unittest.mock import patch

    from app.graph.scene_planner import _call_gemini_planner

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    response_data = [
        {
            "concept": "Solar energy conversion",
            "processKind": "mechanism",
            "visual": {
                "type": "scene-graph",
                "title": "ENERGY CONVERSION",
                "nodes": [
                    {
                        "id": "sunlight",
                        "label": "SUNLIGHT",
                        "x": 200,
                        "y": 150,
                    },
                    {
                        "id": "electricity",
                        "label": "ELECTRICITY",
                        "x": 700,
                        "y": 150,
                    },
                ],
            },
        }
    ]

    with (
        patch("google.genai.Client") as client_class,
        patch("google.genai.types.GenerateContentConfig"),
    ):
        client = client_class.return_value
        client.models.generate_content.return_value.text = json.dumps(
            response_data
        )

        result = _call_gemini_planner(
            [
                {
                    "scene_number": 1,
                    "narration": (
                        "Sunlight is converted into electrical energy."
                    ),
                }
            ],
            "How solar panels work",
        )

    assert result[0] is not None
    assert result[0]["concept"] == "Solar energy conversion"
    assert result[0]["visual"] is None


def test_solar_closing_summary_does_not_overfocus_on_tracking():
    scene = scene_planner_node(
        {
            "topic": "How solar panels turn sunlight into electricity",
            "script": (
                "Whether mounted on a roof or part of a large-scale solar "
                "farm that tracks the sun across the sky, these systems "
                "turn simple sunlight into clean, reliable energy to "
                "power our lives."
            ),
            "approved": True,
        }
    )["scenes"][0]

    description = scene["visual_description"].lower()
    assert "overall solar-power application" in description
    assert "everyday life" in description
    assert "tracking as a secondary detail" in description


def test_solar_tracking_description_focuses_on_following_the_sun():
    scene = scene_planner_node(
        {
            "topic": "How solar panels turn sunlight into electricity",
            "script": (
                "Some solar systems use tracking technology to follow "
                "the sun's path across the sky."
            ),
            "approved": True,
        }
    )["scenes"][0]

    description = scene["visual_description"].lower()
    assert "tracking" in description
    assert "sun's path" in description
    assert "narration" in description


def test_gemini_planner_receives_scene_visual_direction(monkeypatch):
    import json
    from unittest.mock import patch

    from app.graph.scene_planner import _call_gemini_planner

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    response_data = [
        {
            "concept": "Sun tracking",
            "processKind": "mechanism",
            "visual": {
                "type": "flow",
                "title": "SUN TRACKING",
                "nodes": [
                    {"label": "SUN PATH", "icon": "sun"},
                    {"label": "TRACKING PANEL", "icon": "panel"},
                ],
            },
        }
    ]

    with (
        patch("google.genai.Client") as client_class,
        patch("google.genai.types.GenerateContentConfig"),
    ):
        client = client_class.return_value
        client.models.generate_content.return_value.text = json.dumps(
            response_data
        )

        _call_gemini_planner(
            [
                {
                    "scene_number": 1,
                    "narration": (
                        "Tracking technology follows the sun's path."
                    ),
                    "visual_description": (
                        "Illustrate solar tracking technology following "
                        "the sun's path."
                    ),
                }
            ],
            "How solar panels work",
        )

        prompt = client.models.generate_content.call_args.kwargs["contents"]

    assert "Visual direction:" in prompt
    assert "Illustrate solar tracking technology following the sun's path." in prompt


def test_gemini_planner_accepts_registered_indexscan_visual(monkeypatch):
    import json
    from unittest.mock import patch

    from app.graph.scene_planner import _call_gemini_planner

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    response_data = [
        {
            "concept": "Finding a row with an index",
            "processKind": "database",
            "visual": {
                "type": "indexscan",
                "title": "INDEX LOOKUP",
                "values": [42, 7, 19, 88, 3, 56, 71, 25],
                "target": 71,
            },
        }
    ]

    with (
        patch("google.genai.Client") as client_class,
        patch("google.genai.types.GenerateContentConfig"),
    ):
        client = client_class.return_value
        client.models.generate_content.return_value.text = json.dumps(
            response_data
        )

        result = _call_gemini_planner(
            [
                {
                    "scene_number": 1,
                    "narration": (
                        "An index helps the database find a row "
                        "without scanning every row."
                    ),
                }
            ],
            "How Database Indexes Make Queries Faster",
        )

    assert result[0] is not None
    assert result[0]["visual"] == response_data[0]["visual"]

def test_gemini_planner_prompt_guides_indexscan_selection(monkeypatch):
    import json
    from unittest.mock import patch

    from app.graph.scene_planner import _call_gemini_planner

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    with (
        patch("google.genai.Client") as client_class,
        patch("google.genai.types.GenerateContentConfig") as config_class,
    ):
        client = client_class.return_value
        client.models.generate_content.return_value.text = json.dumps([
            {
                "concept": "Finding a row using an index",
                "processKind": "database",
                "visual": {
                    "type": "indexscan",
                    "title": "INDEX LOOKUP",
                    "values": [42, 7, 19, 88, 3, 56, 71, 25],
                    "target": 71,
                },
            }
        ])

        _call_gemini_planner(
            [{
                "scene_number": 1,
                "narration": (
                    "An index helps the database find a row "
                    "without scanning every row."
                ),
            }],
            "How Database Indexes Make Queries Faster",
        )

        system_instruction = config_class.call_args.kwargs["system_instruction"]

    assert '"indexscan"' in system_instruction
    assert "without scanning every row" in system_instruction
    assert "illustrative row IDs" in system_instruction


def test_deterministic_selector_chooses_array_visual_for_bubble_sort():
    from app.graph.scene_planner import _deterministic_library_visual

    visual = _deterministic_library_visual(
        "Bubble sort",
        "Bubble sort compares adjacent values and swaps them when needed.",
    )

    assert visual is not None
    assert visual["type"] == "array"
    assert visual["algorithm"] == "bubble-sort"


def test_deterministic_selector_chooses_indexscan_for_database_index():
    from app.graph.scene_planner import _deterministic_library_visual

    visual = _deterministic_library_visual(
        "Database indexes",
        "An index helps the database find a row without scanning every row.",
    )

    assert visual is not None
    assert visual["type"] == "indexscan"
    assert visual["target"] in visual["values"]


def test_scene_planner_uses_library_visual_without_gemini():
    from app.graph.scene_planner import scene_planner_node

    result = scene_planner_node({
        "approved": True,
        "topic": "Bubble sort",
        "category": "cs",
        "script": (
            "Bubble sort compares adjacent values and swaps them when needed."
        ),
    })

    assert result["scenes"]
    assert result["scenes"][0]["visual"]["type"] == "array"


def test_deterministic_selector_leaves_specialised_topics_alone():
    from app.graph.scene_planner import _deterministic_library_visual

    assert _deterministic_library_visual(
        "How vaccines work",
        "The immune system recognises a pathogen and responds to it.",
    ) is None

    assert _deterministic_library_visual(
        "How solar panels work",
        "Solar panels convert sunlight into electrical energy.",
    ) is None


def test_physics_category_does_not_select_cs_library_visual():
    from app.graph.scene_planner import scene_planner_node

    result = scene_planner_node({
        "approved": True,
        "topic": "Projectile motion",
        "category": "physics",
        "script": (
            "A projectile follows a curved path as it moves through the air."
        ),
    })

    assert result["scenes"]
    visual = result["scenes"][0].get("visual")
    assert visual is None or visual["type"] not in {
        "array", "tree", "chain", "graph", "exchange", "code",
        "architecture", "balancer", "ring", "cache",
        "pipeline", "deploy", "table", "join", "indexscan",
        "replication", "sharding",
    }


def test_scene_planner_keeps_43_word_sentence_intact():
    sentence = (
        "If they are not equal, the half in which the target cannot lie "
        "is eliminated and the search continues on the remaining half, "
        "again taking the middle element to compare to the target value, "
        "and repeating this until the target value is found."
    )

    result = scene_planner_node({
        "topic": "How binary search works",
        "category": "cs",
        "script": sentence,
        "approved": True,
    })

    assert len(result["scenes"]) == 1
    assert result["scenes"][0]["narration"] == sentence

def test_deterministic_selector_chooses_tree_visual_for_binary_search_tree():
    from app.graph.scene_planner import _deterministic_library_visual

    visual = _deterministic_library_visual(
        "Binary search tree",
        "A binary search tree stores values in an ordered tree.",
    )

    assert visual is not None
    assert visual["type"] == "tree"
    assert visual["algorithm"] == "inorder"


def test_binary_search_topic_selects_scene_specific_array_phases():
    from app.graph.scene_planner import _deterministic_library_visual

    cases = [
        (
            "Imagine searching a sorted list for one target value.",
            "overview",
            25,
        ),
        (
            "In computer science, binary search finds a target in a sorted array.",
            "overview",
            25,
        ),
        (
            "Binary search compares the target value to the middle element of the array.",
            "midpoint",
            25,
        ),
        (
            "If they are not equal, the half is eliminated and the search "
            "continues on the remaining half, repeating until the target is found.",
            "elimination",
            25,
        ),
        (
            "If the search ends with the remaining half being empty, "
            "the target is not in the array.",
            "not-found",
            20,
        ),
        (
            "The process has two outcomes: the target is found, or the "
            "remaining candidates become empty.",
            "found",
            25,
        ),
    ]

    for narration, expected_phase, expected_target in cases:
        visual = _deterministic_library_visual(
            "How binary search works",
            narration,
        )

        assert visual is not None, narration
        assert visual["type"] == "array", narration
        assert visual["algorithm"] == "binary-search", narration
        assert visual["phase"] == expected_phase, narration
        assert visual["target"] == expected_target, narration


def test_generic_array_mention_does_not_trigger_bubble_sort():
    from app.graph.scene_planner import _deterministic_library_visual

    visual = _deterministic_library_visual(
        "Arrays",
        "An array stores elements at an index.",
    )

    assert visual is not None
    assert visual["type"] == "array"
    assert visual["algorithm"] == "none"


def test_gemini_cannot_replace_binary_search_with_bubble_sort(monkeypatch):
    from app.graph import scene_planner

    def fake_gemini_planner(scenes, topic):
        return [{
            "concept": "Binary search",
            "processKind": "algorithm",
            "visual": {
                "type": "array",
                "title": "Bubble sort",
                "values": [5, 2, 9, 1, 7, 3],
                "algorithm": "bubble-sort",
            },
        }]

    monkeypatch.setattr(
        scene_planner,
        "_call_gemini_planner",
        fake_gemini_planner,
    )

    result = scene_planner.scene_planner_node({
        "topic": "How binary search works",
        "category": "cs",
        "script": (
            "Binary search compares the target value to the middle "
            "element of a sorted array."
        ),
        "approved": True,
    }, use_gemini_planner=True)

    visual = result["scenes"][0]["visual"]
    assert visual["type"] == "array"
    assert visual["algorithm"] == "binary-search"
    assert visual["phase"] == "midpoint"

def test_gemini_cannot_change_binary_search_array_or_phase(monkeypatch):
    from app.graph import scene_planner

    def fake_gemini_planner(scenes, topic):
        return [{
            "concept": "Binary search",
            "processKind": "algorithm",
            "visual": {
                "type": "array",
                "title": "Alternative binary search",
                "values": [1, 3, 5, 7, 9],
                "algorithm": "binary-search",
                "target": 7,
            },
        }]

    monkeypatch.setattr(
        scene_planner,
        "_call_gemini_planner",
        fake_gemini_planner,
    )

    result = scene_planner.scene_planner_node({
        "topic": "How binary search works",
        "category": "cs",
        "script": (
            "Binary search compares the target value to the middle "
            "element of a sorted array."
        ),
        "approved": True,
    }, use_gemini_planner=True)

    visual = result["scenes"][0]["visual"]

    assert visual["type"] == "array"
    assert visual["algorithm"] == "binary-search"
    assert visual["values"] == [3, 8, 12, 19, 25, 31, 42]
    assert visual["target"] == 25
    assert visual["phase"] == "midpoint"


def test_narration_only_binary_search_visual_includes_phase():
    from app.graph.scene_planner import _deterministic_library_visual

    visual = _deterministic_library_visual(
        "Arrays and searching",
        "Binary search compares the target value to the middle element.",
    )

    assert visual is not None
    assert visual["algorithm"] == "binary-search"
    assert visual["phase"] == "midpoint"
    assert visual["target"] == 25
