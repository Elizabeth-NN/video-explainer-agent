"""Renderer-independent scene graph model and validation."""

from collections.abc import Mapping
from typing import Any


SCENE_GRAPH_SCHEMA_VERSION = 1

RELATIONSHIP_TYPES = frozenset(
    {
        "causes",
        "influences",
        "increases",
        "decreases",
        "transforms",
        "contains",
        "part_of",
        "precedes",
        "follows",
        "connects_to",
        "flows_to",
        "enables",
        "inhibits",
        "feedback_to",
        "unknown",
    }
)

MAX_GRAPH_NODES = 12
MAX_GRAPH_EDGES = 20


class SceneGraphValidationError(ValueError):
    """Raised when a scene graph is structurally invalid."""


def validate_scene_graph(graph: Mapping[str, Any]) -> None:
    """Validate a semantic scene graph without requiring visual coordinates.

    Expected structure:
        {
            "schema_version": 1,
            "nodes": [
                {"id": "water", "label": "Water"},
                {"id": "vapour", "label": "Water vapour"},
            ],
            "edges": [
                {
                    "source": "water",
                    "target": "vapour",
                    "relationship": "transforms",
                }
            ],
        }

    Layout properties such as x, y, colour, and animation timing belong
    to the renderer/layout layer, not this semantic graph model.
    """
    if not isinstance(graph, Mapping):
        raise SceneGraphValidationError("Graph must be a mapping.")

    version = graph.get("schema_version")
    if version != SCENE_GRAPH_SCHEMA_VERSION:
        raise SceneGraphValidationError(
            f"Unsupported graph schema version: {version!r}."
        )

    nodes = graph.get("nodes")
    edges = graph.get("edges")

    if not isinstance(nodes, list) or not nodes:
        raise SceneGraphValidationError(
            "Graph must contain a non-empty nodes list."
        )

    if not isinstance(edges, list):
        raise SceneGraphValidationError("Graph must contain an edges list.")

    if len(nodes) > MAX_GRAPH_NODES:
        raise SceneGraphValidationError(
            f"Graph cannot contain more than {MAX_GRAPH_NODES} nodes."
        )

    if len(edges) > MAX_GRAPH_EDGES:
        raise SceneGraphValidationError(
            f"Graph cannot contain more than {MAX_GRAPH_EDGES} edges."
        )

    node_ids: set[str] = set()

    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            raise SceneGraphValidationError(
                f"Node {index} must be a mapping."
            )

        node_id = node.get("id")
        label = node.get("label")

        if not isinstance(node_id, str) or not node_id.strip():
            raise SceneGraphValidationError(
                f"Node {index} must have a non-empty string ID."
            )

        if node_id in node_ids:
            raise SceneGraphValidationError(
                f"Duplicate node ID: {node_id!r}."
            )

        if not isinstance(label, str) or not label.strip():
            raise SceneGraphValidationError(
                f"Node {node_id!r} must have a non-empty label."
            )

        node_ids.add(node_id)

    for index, edge in enumerate(edges):
        if not isinstance(edge, Mapping):
            raise SceneGraphValidationError(
                f"Edge {index} must be a mapping."
            )

        source = edge.get("source")
        target = edge.get("target")
        relationship = edge.get("relationship")

        if source not in node_ids:
            raise SceneGraphValidationError(
                f"Edge {index} references unknown source node: {source!r}."
            )

        if target not in node_ids:
            raise SceneGraphValidationError(
                f"Edge {index} references unknown target node: {target!r}."
            )

        if source == target:
            raise SceneGraphValidationError(
                f"Edge {index} cannot connect a node to itself."
            )

        if relationship not in RELATIONSHIP_TYPES:
            raise SceneGraphValidationError(
                f"Edge {index} has unsupported relationship: "
                f"{relationship!r}."
            )
