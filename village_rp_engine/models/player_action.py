from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerAction:
    action_type: str
    target_location: str | None = None
    target_npc_id: str | None = None
    target_settlement_id: str | None = None

    @classmethod
    def move(cls, target_location: str) -> "PlayerAction":
        return cls(action_type='move', target_location=target_location)

    @classmethod
    def talk(cls, target_npc_id: str) -> "PlayerAction":
        return cls(action_type='talk', target_npc_id=target_npc_id)

    @classmethod
    def travel(cls, target_settlement_id: str) -> "PlayerAction":
        return cls(action_type='travel', target_settlement_id=target_settlement_id)

    @classmethod
    def wait(cls) -> "PlayerAction":
        return cls(action_type='wait')
