
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
        "research_sources": [],
        "research_quality": "insufficient",
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
    print(f"Research quality: {result.get('research_quality', 'unknown')}")
    print(f"Approved: {result['approved']}")
    print(f"Critique: {result['critique']}")

    print(f"\n=== GENERATED SCRIPT ===\n{result['script']}")

    print("\n=== RESEARCH SOURCES ===")
    sources = result.get("research_sources", [])

    if not sources:
        print("No sources were returned.")
    else:
        for index, source in enumerate(sources, start=1):
            print(f"\n{index}. {source['title']}")
            print(f"   URL: {source['url']}")
            print(f"   Summary: {source['summary']}")

    print("\n=== GENERATED SCENE PLAN ===")
    scenes = result.get("scenes", [])

    if not scenes:
        print("No scenes generated. The script may not have been approved.")
    else:
        total_duration = 0

        for scene in scenes:
            duration = scene["duration_seconds"]
            total_duration += duration

            print(f"\nScene {scene['scene_number']}")
            print(f"Estimated duration: {duration} seconds")
            print(f"Narration: {scene['narration']}")
            print(f"Visual direction: {scene['visual_description']}")

        minutes, seconds = divmod(total_duration, 60)
        print(
            f"\nTotal estimated duration: "
            f"{minutes} min {seconds} sec"
        )

    print("\nNote: Source retrieval does not independently verify every claim.")


if __name__ == "__main__":
    main()
