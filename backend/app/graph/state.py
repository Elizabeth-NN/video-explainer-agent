
from typing import TypedDict


class ResearchSource(TypedDict):
    title: str
    url: str
    summary: str


class VideoState(TypedDict):
    topic: str
    research_notes: list[str]
    research_sources: list[ResearchSource]
    script: str
    critique: str
    approved: bool
    revision_count: int
