"""Convert positioned semantic scene graphs into Remotion visual specs."""

from collections.abc import Mapping
from typing import Any

from app.graph.scene_graph import validate_scene_graph


RELATIONSHIP_LABELS = {
    "causes": "CAUSES",
    "influences": "INFLUENCES",
    "increases": "INCREASES",
    "decreases": "DECREASES",
    "transforms": "TRANSFORMS INTO",
    "contains": "CONTAINS",
    "part_of": "PART OF",
    "precedes": "PRECEDES",
    "follows": "FOLLOWS",
    "connects_to": "CONNECTS TO",
    "flows_to": "FLOWS TO",
    "enables": "ENABLES",
    "inhibits": "INHIBITS",
    "feedback_to": "FEEDBACK TO",
    "unknown": "RELATES TO",
}

NODE_COLORS = ("#4FD1C5", "#F2B84B", "#A78BFA", "#E87979")
LINK_COLOR = "#4FD1C5"


class RemotionAdapterError(ValueError):
    """Raised when a positioned graph cannot be converted to Remotion."""


def to_remotion_visual(
    positioned_graph: Mapping[str, Any],
    *,
    title: str = "How the Ideas Connect",
    footnote: str = "Relationships identified from the narration",
) -> dict[str, Any]:
    """Convert a laid-out semantic graph to Remotion's scene-graph schema.

    Semantic data remains renderer-independent. This function owns only
    presentation choices and the mapping to Remotion's expected field names.
    """
    validate_scene_graph(positioned_graph)

    nodes = positioned_graph["nodes"]
    edges = positioned_graph["edges"]

    for index, node in enumerate(nodes):
        if "x" not in node or "y" not in node:
            raise RemotionAdapterError(
                f"Node {node['id']!r} is missing layout coordinates."
            )

        if not isinstance(node["x"], (int, float)) or not isinstance(
            node["y"], (int, float)
        ):
            raise RemotionAdapterError(
                f"Node {node['id']!r} has invalid layout coordinates."
            )

    node_specs = []
    for index, node in enumerate(nodes):
        node_specs.append(
            {
                "id": node["id"],
                "label": node["label"].strip().upper(),
                "x": node["x"],
                "y": node["y"],
                "size": 38,
                "color": NODE_COLORS[index % len(NODE_COLORS)],
                "appearAt": round(0.2 + index * 0.18, 2),
            }
        )

    link_specs = []
    for index, edge in enumerate(edges):
        relationship = edge["relationship"]
        link_specs.append(
            {
                "from": edge["source"],
                "to": edge["target"],
                "label": RELATIONSHIP_LABELS[relationship],
                "color": LINK_COLOR,
                "style": "dashed" if edge.get("is_feedback") else "solid",
                "appearAt": round(0.4 + index * 0.12, 2),
            }
        )

    result = {
        "type": "scene-graph",
        "title": title,
        "nodes": node_specs,
        "links": link_specs,
    }

    if footnote:
        result["footnote"] = footnote

    return result
