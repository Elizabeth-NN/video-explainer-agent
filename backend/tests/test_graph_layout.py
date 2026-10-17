import pytest

from app.graph.graph_layout import (
    GraphLayoutError,
    layout_scene_graph,
)


def graph_with_edges(edges):
    return {
        "schema_version": 1,
        "nodes": [
            {"id": "a", "label": "Source"},
            {"id": "b", "label": "Middle"},
            {"id": "c", "label": "Outcome"},
        ],
        "edges": edges,
    }


def test_layout_positions_nodes_without_changing_semantic_graph():
    graph = graph_with_edges(
        [
            {
                "source": "a",
                "target": "b",
                "relationship": "causes",
            },
            {
                "source": "b",
                "target": "c",
                "relationship": "transforms",
            },
        ]
    )
    original = repr(graph)

    result = layout_scene_graph(graph)

    assert repr(graph) == original
    assert len(result["nodes"]) == 3
    assert len(result["edges"]) == 2


def test_layout_places_chain_from_left_to_right():
    graph = graph_with_edges(
        [
            {"source": "a", "target": "b", "relationship": "causes"},
            {"source": "b", "target": "c", "relationship": "causes"},
        ]
    )

    result = layout_scene_graph(graph)
    positions = {node["id"]: node["x"] for node in result["nodes"]}

    assert positions["a"] < positions["b"] < positions["c"]


def test_layout_supports_branching_relationships():
    graph = {
        "schema_version": 1,
        "nodes": [
            {"id": "source", "label": "Source"},
            {"id": "left", "label": "Left outcome"},
            {"id": "right", "label": "Right outcome"},
        ],
        "edges": [
            {
                "source": "source",
                "target": "left",
                "relationship": "causes",
            },
            {
                "source": "source",
                "target": "right",
                "relationship": "influences",
            },
        ],
    }

    result = layout_scene_graph(graph)
    positions = {node["id"]: node for node in result["nodes"]}

    assert positions["source"]["x"] < positions["left"]["x"]
    assert positions["source"]["x"] < positions["right"]["x"]
    assert positions["left"]["y"] != positions["right"]["y"]


def test_layout_is_deterministic():
    graph = graph_with_edges(
        [{"source": "a", "target": "b", "relationship": "causes"}]
    )

    assert layout_scene_graph(graph) == layout_scene_graph(graph)


def test_feedback_edge_does_not_control_main_layout_order():
    graph = {
        "schema_version": 1,
        "nodes": [
            {"id": "a", "label": "Input"},
            {"id": "b", "label": "Process"},
            {"id": "c", "label": "Output"},
        ],
        "edges": [
            {"source": "a", "target": "b", "relationship": "causes"},
            {"source": "b", "target": "c", "relationship": "causes"},
            {
                "source": "c",
                "target": "a",
                "relationship": "feedback_to",
            },
        ],
    }

    result = layout_scene_graph(graph)
    positions = {node["id"]: node["x"] for node in result["nodes"]}
    feedback = result["edges"][-1]

    assert positions["a"] < positions["b"] < positions["c"]
    assert feedback["is_feedback"] is True


def test_unmarked_directed_cycle_is_rejected():
    graph = {
        "schema_version": 1,
        "nodes": [
            {"id": "a", "label": "A"},
            {"id": "b", "label": "B"},
        ],
        "edges": [
            {"source": "a", "target": "b", "relationship": "causes"},
            {"source": "b", "target": "a", "relationship": "causes"},
        ],
    }

    with pytest.raises(GraphLayoutError, match="directed cycle"):
        layout_scene_graph(graph)


def test_invalid_canvas_dimensions_are_rejected():
    graph = graph_with_edges([])

    with pytest.raises(GraphLayoutError, match="positive"):
        layout_scene_graph(graph, width=0)


def test_layout_preserves_edge_relationships():
    graph = graph_with_edges(
        [{"source": "a", "target": "b", "relationship": "transforms"}]
    )

    result = layout_scene_graph(graph)

    assert result["edges"][0]["relationship"] == "transforms"
    assert result["edges"][0]["source_x"] < result["edges"][0]["target_x"]
