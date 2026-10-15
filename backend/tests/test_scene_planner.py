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
