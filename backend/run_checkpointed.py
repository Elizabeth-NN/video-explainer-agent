
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

    # A thread ID identifies this workflow's saved state.
    thread_id = str(uuid.uuid4())

    with SqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
        graph = build_graph(checkpointer=checkpointer)

        result = graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": thread_id}},
        )

        print("\n=== CHECKPOINTED VIDEO AGENT ===")
        print(f"Thread ID: {thread_id}")
        print(f"Topic: {result['topic']}")
        print(f"Approved: {result['approved']}")
        print(f"Revisions: {result['revision_count']}")
        print(f"Script: {result['script']}")

        # Read the latest saved snapshot for this thread.
        snapshot = graph.get_state(
            {"configurable": {"thread_id": thread_id}}
        )
        print(f"Checkpoint created: {snapshot.values['topic'] == result['topic']}")


if __name__ == "__main__":
    main()
