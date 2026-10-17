import argparse
import asyncio
from pathlib import Path

from app.graph.workflow import build_graph
from app.services.narration import DEFAULT_VOICE, generate_narration
from app.services.video_renderer import render_video


def main():
    parser = argparse.ArgumentParser(
        description="Generate an explainer-video script and media."
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
    parser.add_argument(
        "--semantic-graphs",
        action="store_true",
        help="Use Gemini to extract semantic graphs for scene visuals.",
    )
    parser.add_argument(
        "--visual-planner",
        action="store_true",
        help="Use Gemini to plan per-scene visuals (concept, processKind, visual spec).",
    )
    parser.add_argument(
        "--audio",
        action="store_true",
        help="Generate MP3 narration for an approved script.",
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="Generate narration and render an MP4 video.",
    )
    parser.add_argument(
        "--voice",
        default=DEFAULT_VOICE,
        help=f"Edge TTS voice (default: {DEFAULT_VOICE}).",
    )
    parser.add_argument(
        "--output-dir",
        default="generated/narration",
        help="Directory for generated audio, manifests, and video.",
    )

    args = parser.parse_args()
    graph = build_graph(
        use_llm=args.gemini,
        use_semantic_graph=args.semantic_graphs,
        use_gemini_planner=args.visual_planner,
    )

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

    # Video generation needs narration, so --video implies --audio.
    if args.audio or args.video:
        if not result.get("approved", False):
            print("\nMedia generation skipped: the script has not been approved.")
        elif not scenes:
            print("\nMedia generation skipped: there are no scenes.")
        else:
            print("\n=== GENERATING NARRATION AUDIO ===")
            manifest = asyncio.run(
                generate_narration(
                    scenes=scenes,
                    output_dir=args.output_dir,
                    voice=args.voice,
                    topic=result["topic"],
                )
            )
            print(f"Audio directory: {args.output_dir}")
            print(f"Combined audio: {manifest['combined_audio_file']}")
            print(
                "Actual audio duration: "
                f"{manifest['total_audio_duration_seconds']} seconds"
            )
            print(
                f"Scene audio files generated: {manifest['scene_count']}"
            )
            print("Audio manifest: manifest.json")

            if args.video:
                print("\n=== RENDERING MP4 VIDEO ===")
                output_path = Path(args.output_dir) / "explainer.mp4"

                video = render_video(
                    scenes=scenes,
                    narration_manifest_path=(
                        Path(args.output_dir) / "manifest.json"
                    ),
                    output_path=output_path,
                    topic=args.topic,
                )

                print(f"Video: {video['output_file']}")
                print(
                    f"Resolution: {video['width']}x{video['height']} "
                    f"at {video['fps']} FPS"
                )
                print(f"Video duration: {video['duration_seconds']} seconds")
                print(f"Scenes rendered: {video['scene_count']}")
                print(
                    "Video metadata: "
                    f"{output_path.with_suffix('.json')}"
                )

    print("\nNote: Source retrieval does not independently verify every claim.")


if __name__ == "__main__":
    main()
