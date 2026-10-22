import os

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



def _gemini_writer_with_fallback(state: VideoState) -> dict:
    """Use Gemini when available; otherwise use the deterministic writer."""
    try:
        return gemini_scriptwriter_node(state)
    except (RuntimeError, ImportError) as exc:
        print(
            "Gemini writer unavailable; using deterministic writer: "
            f"{exc}"
        )
        return scriptwriter_node(state)


def _gemini_critic_with_fallback(state: VideoState) -> dict:
    """Use Gemini review when available; otherwise use the deterministic critic."""
    try:
        return gemini_critic_node(state)
    except (RuntimeError, ImportError) as exc:
        print(
            "Gemini critic unavailable; using deterministic critic: "
            f"{exc}"
        )
        return critic_node(state)


def _resolve_visual_planner(setting: bool | None) -> tuple[bool, str]:
    """Resolve the visual planner switch, plus a reason when it ends up off."""
    if setting is not None:
        return setting, "" if setting else "explicitly disabled"

    env_value = os.getenv("VISUAL_PLANNER", "").strip().lower()
    if env_value in {"off", "0", "false"}:
        return False, f"VISUAL_PLANNER={env_value}"

    if not os.getenv("GEMINI_API_KEY", "").strip():
        return False, "GEMINI_API_KEY is not set"

    return True, ""


def build_graph(
    checkpointer=None,
    use_llm: bool = False,
    use_semantic_graph: bool = False,
    use_gemini_planner: bool | None = None,
):
    """Build the graph with Wikipedia-first, bounded Tavily fallback."""
    use_gemini_planner, disabled_reason = _resolve_visual_planner(
        use_gemini_planner
    )
    if use_gemini_planner:
        print("[visual-planner] enabled")
    else:
        print(f"[visual-planner] disabled ({disabled_reason})")

    graph = StateGraph(VideoState)

    writer = _gemini_writer_with_fallback if use_llm else scriptwriter_node
    critic = _gemini_critic_with_fallback if use_llm else critic_node

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