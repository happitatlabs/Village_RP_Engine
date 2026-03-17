from __future__ import annotations

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.event import TriggeredEvent
from village_rp_engine.models.relationship import Relationship


class RelationshipSystem:
    def __init__(self, min_score: int = -2, max_score: int = 2) -> None:
        self.min_score = min_score
        self.max_score = max_score

    def ensure_initial_relationships(self, state: WorldState) -> None:
        if state.relationships:
            return

        self._set_relationship(state, "village_elder", "guard_captain", 1)
        self._set_relationship(state, "village_elder", "farmer", 1)

    def get_relationship_score(self, state: WorldState, source_npc_id: str, target_npc_id: str) -> int:
        return state.relationships.get((source_npc_id, target_npc_id), 0)

    def apply_event_effects(self, state: WorldState, triggered_events: list[TriggeredEvent]) -> None:
        for event in triggered_events:
            if event.event_id == "argument_at_tavern":
                self.apply_relationship_delta(state, "blacksmith", "farmer", -1)

    def apply_relationship_delta(self, state: WorldState, npc_a: str, npc_b: str, delta: int) -> None:
        next_score = self._clamp(self.get_relationship_score(state, npc_a, npc_b) + delta)
        state.relationships[(npc_a, npc_b)] = next_score
        state.relationships[(npc_b, npc_a)] = next_score
        state.world_log.append(f"관계 변화: {npc_a} ↔ {npc_b} ({next_score:+d})")

    def list_relationships(self, state: WorldState) -> list[Relationship]:
        relationships: list[Relationship] = []
        seen_pairs: set[tuple[str, str]] = set()
        for (source_npc_id, target_npc_id), score in sorted(state.relationships.items()):
            canonical_pair = tuple(sorted((source_npc_id, target_npc_id)))
            if canonical_pair in seen_pairs:
                continue
            seen_pairs.add(canonical_pair)
            relationships.append(
                Relationship(
                    source_npc_id=canonical_pair[0],
                    target_npc_id=canonical_pair[1],
                    score=score,
                )
            )
        return relationships

    def _set_relationship(self, state: WorldState, npc_a: str, npc_b: str, score: int) -> None:
        state.relationships[(npc_a, npc_b)] = score
        state.relationships[(npc_b, npc_a)] = score

    def _clamp(self, score: int) -> int:
        return max(self.min_score, min(self.max_score, score))
