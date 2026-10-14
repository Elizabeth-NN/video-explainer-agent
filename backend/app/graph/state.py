from typing import Literal, TypedDict


class ResearchSource(TypedDict):
    title: str
    url: str
    summary: str


class VideoState(TypedDict):
    topic: str
    research_notes: list[str]
    research_sources: list[ResearchSource]
    research_quality: Literal["insufficient", "limited", "adequate"]
    script: str
    critique: str
    approved: bool
    revision_count: int
