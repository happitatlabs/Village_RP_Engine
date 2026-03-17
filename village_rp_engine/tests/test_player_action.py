from __future__ import annotations

from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules
from village_rp_engine.models.player_action import PlayerAction


def build_engine() -> TickEngine:
    return TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=build_event_definitions(),
        seed=1,
    )


def test_move_action_updates_player_location_before_tick_resolution() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.move("술집"))
    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.tick == 2
    assert state.time_phase == "저녁"
    assert state.player_location == "술집"
    assert [event.event_id for event in state.triggered_events] == ["argument_at_tavern"]
    assert [scene.source_event_id for scene in state.visible_scenes] == ["argument_at_tavern"]


def test_wait_action_keeps_player_location() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.tick == 1
    assert state.player_location == "광장"
    assert "플레이어 행동: 대기 (광장)" in state.world_log
