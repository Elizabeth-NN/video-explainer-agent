import pytest

from app.graph.scene_graph import (
    SCENE_GRAPH_SCHEMA_VERSION,
    SceneGraphValidationError,
    validate_scene_graph,
)


def valid_graph():
    return {
        "schema_version": SCENE_GRAPH_SCHEMA_VERSION,
        "nodes": [
            {"id": "water", "label": "Water"},
            {"id": "vapour", "label": "Water vapour"},
            {"id": "cloud", "label": "Cloud"},
        ],
        "edges": [
            {
                "source": "water",
                "target": "vapour",
                "relationship": "transforms",
            },
            {
                "source": "vapour",
                "target": "cloud",
                "relationship": "transforms",
            },
        ],
    }


def test_valid_multi_node_graph_passes():
    validate_scene_graph(valid_graph())


def test_graph_does_not_require_visual_coordinates():
    graph = valid_graph()

    for node in graph["nodes"]:
        assert "x" not in node
        assert "y" not in node

    validate_scene_graph(graph)


def test_duplicate_node_ids_are_rejected():
    graph = valid_graph()
    graph["nodes"][1]["id"] = "water"

    with pytest.raises(SceneGraphValidationError, match="Duplicate node ID"):
        validate_scene_graph(graph)


def test_edge_with_unknown_source_is_rejected():
    graph = valid_graph()
    graph["edges"][0]["source"] = "missing"

    with pytest.raises(SceneGraphValidationError, match="unknown source"):
        validate_scene_graph(graph)


def test_edge_with_unknown_target_is_rejected():
    graph = valid_graph()
    graph["edges"][0]["target"] = "missing"

    with pytest.raises(SceneGraphValidationError, match="unknown target"):
        validate_scene_graph(graph)


def test_unsupported_relationship_is_rejected():
    graph = valid_graph()
    graph["edges"][0]["relationship"] = "magically_creates"

    with pytest.raises(
        SceneGraphValidationError,
        match="unsupported relationship",
    ):
        validate_scene_graph(graph)


def test_self_referencing_edge_is_rejected():
    graph = valid_graph()
    graph["edges"][0]["target"] = graph["edges"][0]["source"]

    with pytest.raises(SceneGraphValidationError, match="itself"):
        validate_scene_graph(graph)


def test_empty_nodes_are_rejected():
    graph = valid_graph()
    graph["nodes"] = []
    graph["edges"] = []

    with pytest.raises(SceneGraphValidationError, match="non-empty nodes"):
        validate_scene_graph(graph)


def test_missing_schema_version_is_rejected():
    graph = valid_graph()
    del graph["schema_version"]

    with pytest.raises(SceneGraphValidationError, match="schema version"):
        validate_scene_graph(graph)
