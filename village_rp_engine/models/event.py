from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventDefinition:
    event_id: str
    time_phase: str
    location: str
    required_actor_ids: tuple[str, ...]
    outcome_text: str
    rumor_text: str
    narration_text: str
    observer_narration_text: str
    probability: float = 1.0
    cooldown_tick: int = 0
    rumor_base_score: int = 0


@dataclass
class TriggeredEvent:
    event_id: str
    time_phase: str
    location: str
    actor_ids: tuple[str, ...]
    outcome_text: str
    rumor_text: str
    narration_text: str
    observer_narration_text: str
    rumor_base_score: int = 0
    witnessed: bool = False
