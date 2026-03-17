from __future__ import annotations

from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules
from village_rp_engine.logs.world_log import format_tick_summary
from village_rp_engine.systems.relationship_system import RelationshipSystem


def build_engine() -> TickEngine:
    return TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=build_event_definitions(),
        seed=1,
    )


def test_relationship_initializes_neutral() -> None:
    state = create_initial_world_state()
    relationship_system = RelationshipSystem()

    assert relationship_system.get_relationship_score(state, "blacksmith", "farmer") == 0
    assert relationship_system.get_relationship_score(state, "farmer", "blacksmith") == 0


def test_argument_event_reduces_relationship() -> None:
    engine = build_engine()
    relationship_system = RelationshipSystem()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state)
    state = engine.run_tick(state)

    assert relationship_system.get_relationship_score(state, "blacksmith", "farmer") == -1


def test_relationship_change_accumulates_with_repeated_event() -> None:
    engine = build_engine()
    relationship_system = RelationshipSystem()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state)
    state = engine.run_tick(state)
    assert relationship_system.get_relationship_score(state, "blacksmith", "farmer") == -1

    state.npc_recent_states = {}
    state = engine.run_tick(state)
    state = engine.run_tick(state)
    state = engine.run_tick(state)
    state = engine.run_tick(state)
    state = engine.run_tick(state)

    assert state.time_phase == "저녁"
    assert relationship_system.get_relationship_score(state, "blacksmith", "farmer") == -2


def test_relationship_is_symmetric() -> None:
    engine = build_engine()
    relationship_system = RelationshipSystem()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state)
    state = engine.run_tick(state)

    assert relationship_system.get_relationship_score(state, "blacksmith", "farmer") == -1
    assert relationship_system.get_relationship_score(state, "farmer", "blacksmith") == -1


def test_relationship_output_visible_in_summary_or_log() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state)
    state = engine.run_tick(state)
    summary = format_tick_summary(state)

    assert "Relationships:" in summary
    assert "blacksmith ↔ farmer: -1" in summary
    assert "관계 변화: blacksmith ↔ farmer (-1)" in state.world_log


def test_relationship_and_recent_state_can_coexist() -> None:
    engine = build_engine()
    relationship_system = RelationshipSystem()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state)
    state = engine.run_tick(state)

    assert relationship_system.get_relationship_score(state, "blacksmith", "farmer") == -1
    assert state.npc_recent_states["farmer"][0].state_id == "complaining_about_blacksmith"
    assert state.npc_recent_states["blacksmith"][0].state_id == "irritated_with_farmer"
