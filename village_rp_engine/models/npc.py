from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NPC:
    npc_id: str
    name: str
    role: str
    influence: str = "medium"
    influence_score: int = 0
