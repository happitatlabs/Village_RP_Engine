from __future__ import annotations

from village_rp_engine.core.world_state import WorldState
from village_rp_engine.models.player_notice import PlayerNotice


class NoticeSystem:
    def expire_notices(self, state: WorldState, next_tick: int) -> None:
        active_notices: list[PlayerNotice] = []
        for notice in state.player_notices:
            if notice.expires_tick < next_tick:
                state.world_log.append(f"인지 만료: {notice.observer_npc_id} -> {notice.notice_type}")
                continue
            active_notices.append(notice)
        state.player_notices = active_notices

    def create_player_notices(self, state: WorldState) -> None:
        if state.time_phase != "새벽":
            return

        for npc_id, location in state.npc_locations.items():
            if location != state.player_location:
                continue
            if self._has_active_notice(state, npc_id, "noticed_player_at_dawn"):
                continue
            notice = PlayerNotice(
                observer_npc_id=npc_id,
                target_type="player",
                notice_type="noticed_player_at_dawn",
                location=location,
                time_phase=state.time_phase,
                created_tick=state.tick,
                expires_tick=state.tick,
            )
            state.player_notices.append(notice)
            state.world_log.append(f"인지 기록: {npc_id} -> player ({notice.notice_type})")

    def get_active_notice(self, state: WorldState, observer_npc_id: str) -> PlayerNotice | None:
        for notice in state.player_notices:
            if notice.observer_npc_id == observer_npc_id and notice.target_type == "player":
                return notice
        return None

    def _has_active_notice(self, state: WorldState, observer_npc_id: str, notice_type: str) -> bool:
        return any(
            notice.observer_npc_id == observer_npc_id
            and notice.target_type == "player"
            and notice.notice_type == notice_type
            for notice in state.player_notices
        )
