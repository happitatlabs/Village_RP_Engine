from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerNotice:
    observer_npc_id: str
    target_type: str
    notice_type: str
    location: str
    time_phase: str
    created_tick: int
    expires_tick: int
