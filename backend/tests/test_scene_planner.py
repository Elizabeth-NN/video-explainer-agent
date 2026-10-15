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
