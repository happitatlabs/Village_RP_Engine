from __future__ import annotations

from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules


def test_argument_event_triggers_in_tavern_at_evening() -> None:
    engine = TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=build_event_definitions(),
        seed=1,
    )
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state)
    state = engine.run_tick(state)

    event_ids = [event.event_id for event in state.triggered_events]

    assert state.time_phase == "저녁"
    assert "argument_at_tavern" in event_ids
    assert state.visible_scenes
