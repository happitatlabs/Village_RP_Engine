from __future__ import annotations

from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules


def test_time_phase_cycles_in_order() -> None:
    engine = TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=build_event_definitions(),
        seed=1,
    )
    state = create_initial_world_state()

    phases = []
    for _ in range(6):
        state = engine.run_tick(state)
        phases.append(state.time_phase)

    assert state.day == 2
    assert phases == ["낮", "저녁", "밤", "새벽", "아침", "낮"]
