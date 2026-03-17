from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rumor:
    source_event_id: str
    tick: int
    day: int
    time_phase: str
    location: str
    text: str
