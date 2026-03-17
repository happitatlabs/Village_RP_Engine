from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NPCRecentState:
    npc_id: str
    state_id: str
    source_event_id: str
    expires_day: int
