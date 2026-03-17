from __future__ import annotations

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.event import TriggeredEvent
from village_rp_engine.models.npc_state import NPCRecentState


class AftermathSystem:
    def expire_states(self, state: WorldState, current_day: int) -> None:
        next_states: dict[str, list[NPCRecentState]] = {}
        for npc_id, states in state.npc_recent_states.items():
            active_states: list[NPCRecentState] = []
            for npc_state in states:
                if npc_state.expires_day < current_day:
                    state.world_log.append(f"상태 만료: {npc_id} -> {npc_state.state_id}")
                    continue
                active_states.append(npc_state)
            if active_states:
                next_states[npc_id] = active_states
        state.npc_recent_states = next_states

    def apply_event_effects(self, state: WorldState, triggered_events: list[TriggeredEvent]) -> None:
        for event in triggered_events:
            if event.event_id == "argument_at_tavern":
                self.assign_state(
                    state,
                    npc_id="farmer",
                    state_id="complaining_about_blacksmith",
                    source_event_id=event.event_id,
                    expires_day=state.day + 1,
                )
                self.assign_state(
                    state,
                    npc_id="blacksmith",
                    state_id="irritated_with_farmer",
                    source_event_id=event.event_id,
                    expires_day=state.day + 1,
                )
                self.assign_state(
                    state,
                    npc_id="village_elder",
                    state_id="concerned_about_tavern_argument",
                    source_event_id=event.event_id,
                    expires_day=state.day + 1,
                )

    def assign_state(
        self,
        state: WorldState,
        npc_id: str,
        state_id: str,
        source_event_id: str,
        expires_day: int,
    ) -> None:
        npc_state = NPCRecentState(
            npc_id=npc_id,
            state_id=state_id,
            source_event_id=source_event_id,
            expires_day=expires_day,
        )
        existing_states = [existing for existing in state.npc_recent_states.get(npc_id, []) if existing.state_id != state_id]
        state.npc_recent_states[npc_id] = [*existing_states, npc_state]
        state.world_log.append(f"상태 부여: {npc_id} -> {state_id} (expires_day={expires_day})")

    def get_recent_state(self, state: WorldState, npc_id: str) -> NPCRecentState | None:
        npc_states = state.npc_recent_states.get(npc_id, [])
        if not npc_states:
            return None
        return npc_states[0]
