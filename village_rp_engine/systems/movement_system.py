from __future__ import annotations

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.npc import NPC


class MovementSystem:
    def __init__(self, npcs: list[NPC], schedules: dict[str, dict[str, str]]) -> None:
        self.npcs = npcs
        self.schedules = schedules

    def resolve_locations_for_phase(self, time_phase: str) -> dict[str, str]:
        npc_locations: dict[str, str] = {}
        for npc in self.npcs:
            npc_locations[npc.npc_id] = self.schedules[npc.npc_id][time_phase]
        return npc_locations

    def move_npcs(self, state: WorldState) -> dict[str, str]:
        scheduled_locations = self.resolve_locations_for_phase(state.time_phase)
        npc_locations: dict[str, str] = {}
        for npc in self.npcs:
            if npc.npc_id in state.locked_npc_ids_for_tick:
                current_location = state.npc_locations.get(npc.npc_id, scheduled_locations[npc.npc_id])
                npc_locations[npc.npc_id] = current_location
                state.world_log.append(f"이동 보류: {npc.name} -> {current_location}")
                continue

            override_location = self._resolve_state_override_location(state, npc.npc_id)
            npc_locations[npc.npc_id] = override_location or scheduled_locations[npc.npc_id]
            state.world_log.append(f"이동: {npc.name} -> {npc_locations[npc.npc_id]}")
        return npc_locations

    def _resolve_state_override_location(self, state: WorldState, npc_id: str) -> str | None:
        active_state_ids = {npc_state.state_id for npc_state in state.npc_recent_states.get(npc_id, [])}
        if npc_id == "farmer" and state.time_phase == "저녁" and "complaining_about_blacksmith" in active_state_ids:
            return "광장"
        if npc_id == "blacksmith" and state.time_phase == "저녁" and "irritated_with_farmer" in active_state_ids:
            return "대장간"
        if npc_id == "guard_captain" and state.time_phase in {"밤", "새벽"} and "watchful_after_tavern_argument" in active_state_ids:
            return "술집"
        return None
