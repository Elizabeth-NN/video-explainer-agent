from typing import Any, Literal, NotRequired, TypedDict


class ResearchSource(TypedDict):
    title: str
    url: str
    summary: str


class Scene(TypedDict):
    scene_number: int
    narration: str
    visual_description: str
    duration_seconds: int
    visual: NotRequired[dict[str, Any]]
    concept: NotRequired[str]
    processKind: NotRequired[str]


class VideoState(TypedDict):
    topic: str
    research_notes: list[str]
    research_sources: list[ResearchSource]
    research_quality: Literal["insufficient", "limited", "adequate"]
    script: str
    critique: str
    approved: bool
    revision_count: int
    scenes: list[Scene]
