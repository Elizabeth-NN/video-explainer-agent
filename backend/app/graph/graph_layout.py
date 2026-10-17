"""Deterministic, renderer-independent layout for semantic scene graphs."""

from collections import defaultdict, deque
from collections.abc import Mapping
from typing import Any

from app.graph.scene_graph import validate_scene_graph


CANVAS_WIDTH = 1000
CANVAS_HEIGHT = 430
HORIZONTAL_PADDING = 150
VERTICAL_PADDING = 75


class GraphLayoutError(ValueError):
    """Raised when a graph cannot be laid out by the current algorithm."""


def layout_scene_graph(
    graph: Mapping[str, Any],
    *,
    width: int = CANVAS_WIDTH,
    height: int = CANVAS_HEIGHT,
) -> dict[str, Any]:
    """Return positioned nodes and edges without mutating the input graph.

    The main graph is arranged in left-to-right layers. Edges with the
    relationship type 'feedback_to' are excluded from layer calculation
    so feedback loops do not determine the main reading order.
    """
    validate_scene_graph(graph)

    if width <= 0 or height <= 0:
        raise GraphLayoutError("Canvas dimensions must be positive.")

    nodes = graph["nodes"]
    edges = graph["edges"]
    node_ids = [node["id"] for node in nodes]

    outgoing: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, list[str]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in node_ids}

    for edge in edges:
        if edge["relationship"] == "feedback_to":
            continue

        source = edge["source"]
        target = edge["target"]
        outgoing[source].append(target)
        incoming[target].append(source)
        indegree[target] += 1

    # Stable topological traversal: input order breaks ties consistently.
    order_index = {node_id: index for index, node_id in enumerate(node_ids)}
    ready = deque(
        sorted(
            (node_id for node_id in node_ids if indegree[node_id] == 0),
            key=order_index.__getitem__,
        )
    )

    layers = {node_id: 0 for node_id in node_ids}
    visited: list[str] = []

    while ready:
        node_id = ready.popleft()
        visited.append(node_id)

        for target in sorted(outgoing[node_id], key=order_index.__getitem__):
            layers[target] = max(layers[target], layers[node_id] + 1)
            indegree[target] -= 1

            if indegree[target] == 0:
                ready.append(target)

    if len(visited) != len(node_ids):
        raise GraphLayoutError(
            "The main graph contains a directed cycle. "
            "Mark intentional feedback relationships as 'feedback_to'."
        )

    max_layer = max(layers.values(), default=0)
    layer_count = max_layer + 1

    left = min(HORIZONTAL_PADDING, width / 2)
    right = max(width - HORIZONTAL_PADDING, width / 2)

    if layer_count == 1:
        x_positions = {0: width / 2}
    else:
        usable_width = right - left
        x_positions = {
            layer: left + usable_width * layer / max_layer
            for layer in range(layer_count)
        }

    nodes_by_layer: dict[int, list[str]] = defaultdict(list)

    for node_id in node_ids:
        nodes_by_layer[layers[node_id]].append(node_id)

    positioned_nodes = []

    for layer in range(layer_count):
        layer_nodes = nodes_by_layer[layer]
        count = len(layer_nodes)

        top = min(VERTICAL_PADDING, height / 2)
        bottom = max(height - VERTICAL_PADDING, height / 2)

        if count == 1:
            y_positions = [height / 2]
        else:
            usable_height = bottom - top
            y_positions = [
                top + usable_height * index / (count - 1)
                for index in range(count)
            ]

        for node_id, y in zip(layer_nodes, y_positions):
            original = next(node for node in nodes if node["id"] == node_id)
            positioned_nodes.append(
                {
                    **original,
                    "x": round(x_positions[layer]),
                    "y": round(y),
                }
            )

    positioned_by_id = {
        node["id"]: node for node in positioned_nodes
    }

    positioned_edges = []

    for edge in edges:
        source = positioned_by_id[edge["source"]]
        target = positioned_by_id[edge["target"]]

        positioned_edges.append(
            {
                **edge,
                "source_x": source["x"],
                "source_y": source["y"],
                "target_x": target["x"],
                "target_y": target["y"],
                "is_feedback": edge["relationship"] == "feedback_to",
            }
        )

    return {
        "schema_version": graph["schema_version"],
        "width": width,
        "height": height,
        "nodes": positioned_nodes,
        "edges": positioned_edges,
    }
