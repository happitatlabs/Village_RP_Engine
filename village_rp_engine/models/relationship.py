from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Relationship:
    source_npc_id: str
    target_npc_id: str
    score: int
