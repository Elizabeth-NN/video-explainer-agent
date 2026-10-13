
import argparse

from app.graph.workflow import build_graph


def main():
    parser = argparse.ArgumentParser(
        description="Generate an explainer-video script."
    )

    parser.add_argument(
        "topic",
        nargs="?",
        default="How vaccines work",
        help="Topic to explain in the video.",
    )

    parser.add_argument(
        "--gemini",
        action="store_true",
        help="Use Google's Gemini API to generate the script.",
    )

    args = parser.parse_args()

    graph = build_graph(use_llm=args.gemini)

    initial_state = {
        "topic": args.topic,
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

    writer = "Google Gemini" if args.gemini else "Deterministic fallback"

    print("\n=== EXPLAINER VIDEO AGENT ===")
    print(f"Topic: {result['topic']}")
    print(f"Scriptwriter: {writer}")
    print(f"Revisions: {result['revision_count']}")
    print(f"Approved: {result['approved']}")
    print(f"Critique: {result['critique']}")
    print(f"\nScript:\n{result['script']}")

    print("\nResearch notes:")
    for note in result["research_notes"]:
        print(f"- {note}")


if __name__ == "__main__":
    main()
