from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scene:
    source_event_id: str | None
    tick: int
    location: str
    text: str
    observer_text: str
