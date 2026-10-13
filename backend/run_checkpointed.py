import uuid

from langgraph.checkpoint.sqlite import SqliteSaver

from app.graph.workflow import build_graph


def main():
    initial_state = {
        "topic": "How vaccines work",
        "research_notes": [],
        "script": "",
        "critique": "",
        "approved": False,
        "revision_count": 0,
    }

    # Give this workflow run its own conversation/thread ID.
    thread_id = str(uuid.uuid4())

    # SQLite stores checkpoints in this local database file.
    with SqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
        graph = build_graph().copy() if False else build_graph()

        # Recompile the graph with checkpointing enabled.
        from langgraph.graph import END, START, StateGraph
        from app.graph.nodes import (
            critic_node,
            research_node,
            revise_script_node,
            scriptwriter_node,
        )
        from app.graph.state import VideoState

        builder = StateGraph(VideoState)
        builder.add_node("research", research_node)
        builder.add_node("scriptwriter", scriptwriter_node)
        builder.add_node("critic", critic_node)
        builder.add_node("revise_script", revise_script_node)

        builder.add_edge(START, "research")
        builder.add_edge("research", "scriptwriter")
        builder.add_edge("scriptwriter", "critic")
        builder.add_conditional_edges(
            "critic",
            lambda state: (
                "approved"
                if state["approved"]
                else "failed"
                if state["revision_count"] >= 2
                else "revise"
            ),
            {
                "approved": END,
                "revise": "revise_script",
                "failed": END,
            },
        )
        builder.add_edge("revise_script", "critic")

        checkpointed_graph = builder.compile(checkpointer=checkpointer)

        result = checkpointed_graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
        )

        print("\n=== CHECKPOINTED VIDEO AGENT ===")
        print(f"Thread ID: {thread_id}")
        print(f"Topic: {result['topic']}")
        print(f"Approved: {result['approved']}")
        print(f"Revisions: {result['revision_count']}")
        print(f"Script: {result['script']}")
        print("\nCheckpointing is enabled.")

if __name__ == "__main__":
    main()
