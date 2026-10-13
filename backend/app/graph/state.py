
from typing import TypedDict


class VideoState(TypedDict):
    topic: str
    research_notes: list[str]
    script: str
    critique: str
    approved: bool
    revision_count: int
