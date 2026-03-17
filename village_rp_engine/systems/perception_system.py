from __future__ import annotations

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.event import TriggeredEvent


class PerceptionSystem:
    def split_events_by_visibility(
        self,
        state: WorldState,
        events: list[TriggeredEvent],
    ) -> tuple[list[TriggeredEvent], list[TriggeredEvent]]:
        visible: list[TriggeredEvent] = []
        hidden: list[TriggeredEvent] = []

        for event in events:
            event.witnessed = event.location == state.player_location
            if event.witnessed:
                visible.append(event)
                state.world_log.append(f"플레이어 목격: {event.event_id}")
            else:
                hidden.append(event)
                state.world_log.append(f"플레이어 비목격: {event.event_id}")

        return visible, hidden
