
from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    critic_node,
    gemini_scriptwriter_node,
    research_node,
    revise_script_node,
    scriptwriter_node,
)
from app.graph.state import VideoState


def route_after_critique(state: VideoState) -> str:
    if state["approved"]:
        return "approved"

    if state.get("research_quality") == "insufficient":
        return "insufficient_research"

    if state["revision_count"] >= 2:
        return "failed"

    return "revise"


def build_graph(checkpointer=None, use_llm: bool = False):
    """Build the graph with either Gemini or the deterministic scriptwriter."""
    graph = StateGraph(VideoState)

    graph.add_node("research", research_node)

    writer = gemini_scriptwriter_node if use_llm else scriptwriter_node
    graph.add_node("scriptwriter", writer)

    graph.add_node("critic", critic_node)
    graph.add_node(
        "revise_script",
        lambda state: revise_script_node(state, writer=writer),
    )

    graph.add_edge(START, "research")
    graph.add_edge("research", "scriptwriter")
    graph.add_edge("scriptwriter", "critic")

    graph.add_conditional_edges(
        "critic",
        route_after_critique,
        {
            "approved": END,
            "insufficient_research": END,
            "revise": "revise_script",
            "failed": END,
        },
    )

    graph.add_edge("revise_script", "critic")

    return graph.compile(checkpointer=checkpointer)
