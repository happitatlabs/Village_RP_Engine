from __future__ import annotations

from village_rp_engine.config import PUBLIC_LOCATIONS
from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.player_action import PlayerAction


class PlayerActionSystem:
    def apply_action(self, state: WorldState, action: PlayerAction) -> None:
        if action.action_type == "wait":
            state.world_log.append(f"플레이어 행동: 대기 ({state.player_location})")
            return

        if action.action_type == "move" and action.target_location in PUBLIC_LOCATIONS:
            state.player_location = action.target_location
            state.world_log.append(f"플레이어 행동: 이동 -> {action.target_location}")
            return

        if action.action_type == "talk" and action.target_npc_id:
            state.world_log.append(f"플레이어 행동: 대화 시도 -> {action.target_npc_id}")
            return

        raise ValueError(f"지원하지 않는 플레이어 행동: {action}")
