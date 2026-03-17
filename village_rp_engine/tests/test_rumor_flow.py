from __future__ import annotations

from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules


def test_unwitnessed_argument_event_becomes_rumor() -> None:
    engine = TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=build_event_definitions(),
        seed=1,
    )
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state)
    state = engine.run_tick(state)

    rumor_event_ids = [rumor.source_event_id for rumor in state.rumor_log]

    assert state.day == 1
    assert state.time_phase == "저녁"
    assert "argument_at_tavern" in rumor_event_ids
    assert not state.visible_scenes


def test_morning_chat_does_not_create_rumor() -> None:
    engine = TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=build_event_definitions(),
        seed=1,
    )
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state)

    assert state.time_phase == "낮"
    assert state.rumor_log == []
