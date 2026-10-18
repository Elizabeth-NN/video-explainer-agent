from langgraph.graph import END, START, StateGraph

from app.graph.scene_planner import scene_planner_node
from app.graph.nodes import (
    critic_node,
    gemini_critic_node,
    gemini_scriptwriter_node,
    research_node,
    revise_script_node,
    scriptwriter_node,
    tavily_research_node,
)
from app.graph.state import VideoState


def route_after_research(state: VideoState) -> str:
    """Use Tavily once when Wikipedia evidence is insufficient."""
    if (
        not state.get("tavily_used", False)
        and (
            state.get("research_quality") == "insufficient"
            or len(state.get("research_sources", [])) < 2
        )
    ):
        return "tavily"

    if state.get("research_quality") == "insufficient":
        return "insufficient_research"

    return "scriptwriter"


def route_after_tavily(state: VideoState) -> str:
    """Continue only if enough usable evidence is available."""
    if (
        state.get("research_quality") == "insufficient"
        or len(state.get("research_sources", [])) < 2
    ):
        return "insufficient_research"

    return "scriptwriter"


def route_after_critique(state: VideoState) -> str:
    if state["approved"]:
        return "approved"

    categories = set(state.get("critic_categories", []))
    evidence_gap = bool(
        categories.intersection({"research_gap", "unsupported_claims"})
    )

    # A critic-identified evidence gap may trigger one Tavily attempt.
    if evidence_gap and not state.get("tavily_used", False):
        return "tavily"

    if state.get("research_quality") == "insufficient":
        return "insufficient_research"

    if state["revision_count"] >= 2:
        return "failed"

    return "revise"


def insufficient_research_node(state: VideoState) -> dict:
    """Stop safely when neither source can provide enough evidence."""
    existing_critique = state.get("critique", "").strip()
    message = (
        "Research coverage is insufficient. Wikipedia and the available "
        "fallback research did not provide enough usable evidence to "
        "produce a reliable explainer."
    )

    if existing_critique:
        message = f"{existing_critique} {message}"

    return {
        "approved": False,
        "critique": message,
        "tavily_used": state.get("tavily_used", False),
    }


def build_graph(
    checkpointer=None,
    use_llm: bool = False,
    use_semantic_graph: bool = False,
    use_gemini_planner: bool = False,
):
    """Build the graph with Wikipedia-first, bounded Tavily fallback."""
    graph = StateGraph(VideoState)

    writer = gemini_scriptwriter_node if use_llm else scriptwriter_node
    critic = gemini_critic_node if use_llm else critic_node

    graph.add_node("research", research_node)
    graph.add_node("tavily", tavily_research_node)
    graph.add_node("insufficient_research", insufficient_research_node)
    graph.add_node("scriptwriter", writer)
    graph.add_node("critic", critic)

    graph.add_node(
        "scene_planner",
        lambda state: scene_planner_node(
            state,
            use_semantic_graph=use_semantic_graph,
            use_gemini_planner=use_gemini_planner,
        ),
    )
    graph.add_node(
        "revise_script",
        lambda state: revise_script_node(state, writer=writer),
    )

    graph.add_edge(START, "research")

    graph.add_conditional_edges(
        "research",
        route_after_research,
        {
            "tavily": "tavily",
            "scriptwriter": "scriptwriter",
            "insufficient_research": "insufficient_research",
        },
    )

    graph.add_conditional_edges(
        "tavily",
        route_after_tavily,
        {
            "scriptwriter": "scriptwriter",
            "insufficient_research": "insufficient_research",
        },
    )

    graph.add_edge("scriptwriter", "critic")

    graph.add_conditional_edges(
        "critic",
        route_after_critique,
        {
            "approved": "scene_planner",
            "tavily": "tavily",
            "insufficient_research": "insufficient_research",
            "revise": "revise_script",
            "failed": END,
        },
    )

    graph.add_edge("revise_script", "critic")
    graph.add_edge("scene_planner", END)
    graph.add_edge("insufficient_research", END)

    return graph.compile(checkpointer=checkpointer)