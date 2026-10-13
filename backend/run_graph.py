
from app.graph.workflow import build_graph


def main():
    graph = build_graph()

    initial_state = {
        "topic": "How vaccines work",
        "research_notes": [],
        "script": "",
        "critique": "",
        "approved": False,
        "revision_count": 0,
    }

    result = graph.invoke(
        initial_state,
        config={"recursion_limit": 10},
    )

    print("\n=== EXPLAINER VIDEO AGENT ===")
    print(f"Topic: {result['topic']}")
    print(f"Revisions: {result['revision_count']}")
    print(f"Approved: {result['approved']}")
    print(f"Critique: {result['critique']}")
    print(f"\nScript:\n{result['script']}")
    print("\nResearch notes:")
    for note in result["research_notes"]:
        print(f"- {note}")


if __name__ == "__main__":
    main()
