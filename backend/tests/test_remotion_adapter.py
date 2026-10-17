import pytest

from app.graph.graph_layout import layout_scene_graph
from app.graph.remotion_adapter import (
    RemotionAdapterError,
    to_remotion_visual,
)


def sample_graph():
    return {
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


def test_adapter_produces_remotion_scene_graph():
    positioned = layout_scene_graph(sample_graph())

    result = to_remotion_visual(positioned)

    assert result["type"] == "scene-graph"
    assert result["title"] == "How the Ideas Connect"
    assert len(result["nodes"]) == 2
    assert len(result["links"]) == 1


def test_adapter_preserves_node_ids_and_layout_coordinates():
    positioned = layout_scene_graph(sample_graph())

    result = to_remotion_visual(positioned)

    source = next(node for node in result["nodes"] if node["id"] == "energy")
    original = next(node for node in positioned["nodes"] if node["id"] == "energy")

    assert source["x"] == original["x"]
    assert source["y"] == original["y"]
    assert source["label"] == "ENERGY"


def test_adapter_maps_relationship_to_readable_link_label():
    positioned = layout_scene_graph(sample_graph())

    result = to_remotion_visual(positioned)

    assert result["links"][0]["from"] == "energy"
    assert result["links"][0]["to"] == "temperature"
    assert result["links"][0]["label"] == "INCREASES"


def test_adapter_applies_presentation_defaults():
    positioned = layout_scene_graph(sample_graph())

    result = to_remotion_visual(
        positioned,
        title="Energy and Temperature",
        footnote="Illustrative relationship",
    )

    assert result["title"] == "Energy and Temperature"
    assert result["footnote"] == "Illustrative relationship"
    assert result["nodes"][0]["size"] == 38
    assert result["nodes"][0]["color"]
    assert result["links"][0]["style"] == "solid"


def test_adapter_can_omit_footnote():
    positioned = layout_scene_graph(sample_graph())

    result = to_remotion_visual(positioned, footnote="")

    assert "footnote" not in result


def test_adapter_rejects_graph_without_layout_coordinates():
    graph = sample_graph()

    with pytest.raises(RemotionAdapterError):
        to_remotion_visual(graph)


def test_adapter_rejects_invalid_semantic_graph():
    graph = {
        "schema_version": 1,
        "nodes": [{"id": "a", "label": "A"}],
        "edges": [
            {
                "source": "a",
                "target": "missing",
                "relationship": "causes",
            }
        ],
    }

    with pytest.raises(ValueError, match="unknown target"):
        to_remotion_visual(graph)
