from __future__ import annotations

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.event import TriggeredEvent
from village_rp_engine.models.npc import NPC
from village_rp_engine.models.rumor import Rumor


class RumorSystem:
    def __init__(self, npcs: list[NPC]) -> None:
        self.influence_scores = {npc.npc_id: npc.influence_score for npc in npcs}

    def create_rumors(self, state: WorldState, hidden_events: list[TriggeredEvent]) -> list[Rumor]:
        rumors: list[Rumor] = []
        for event in hidden_events:
            rumor_key = f"{event.event_id}:{state.day}"
            if rumor_key in state.rumor_history_keys:
                continue

            rumor_score, max_influence = self._calculate_rumor_score(event)
            should_create = rumor_score >= 2
            state.world_log.append(
                f"소문 판정: {event.event_id} base={event.rumor_base_score} influence={max_influence} total={rumor_score} -> {'생성' if should_create else '생성 안 함'}"
            )
            if not should_create:
                continue

            rumor = Rumor(
                source_event_id=event.event_id,
                tick=state.tick,
                day=state.day,
                time_phase=state.time_phase,
                location=event.location,
                text=event.rumor_text,
            )
            rumors.append(rumor)
            state.rumor_history_keys.add(rumor_key)
            state.world_log.append(f"소문 생성: {rumor.text}")
        return rumors

    def _calculate_rumor_score(self, event: TriggeredEvent) -> tuple[int, int]:
        max_influence = 0
        for actor_id in event.actor_ids:
            max_influence = max(max_influence, self.influence_scores.get(actor_id, 0))
        return event.rumor_base_score + max_influence, max_influence
