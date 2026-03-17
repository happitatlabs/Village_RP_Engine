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


def test_argument_event_assigns_recent_states() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.npc_recent_states["farmer"][0].state_id == "complaining_about_blacksmith"
    assert state.npc_recent_states["blacksmith"][0].state_id == "irritated_with_farmer"
    assert "상태 부여: farmer -> complaining_about_blacksmith (expires_day=2)" in state.world_log


def test_recent_state_affects_dialogue_priority() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.move("대장간"))
    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.talk("blacksmith"))

    assert state.day == 2
    assert state.time_phase == "낮"
    assert state.dialogues[-1].text == "괜한 말이 너무 많아."


def test_recent_state_dialogue_on_talk() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.move("광장"))
    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.talk("farmer"))

    assert state.day == 2
    assert state.time_phase == "낮"
    assert state.dialogues[-1].text == "대장장이랑은 한동안 말 섞기 싫어."


def test_recent_state_expires_after_day_passes() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())
    assert "farmer" in state.npc_recent_states

    engine.event_system.event_definitions = []
    for _ in range(8):
        state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.day == 3
    assert state.npc_recent_states == {}
    assert "상태 만료: farmer -> complaining_about_blacksmith" in state.world_log
    assert "상태 만료: blacksmith -> irritated_with_farmer" in state.world_log


def test_recent_state_expires_and_default_dialogue_returns() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())
    engine.event_system.event_definitions = []
    for _ in range(8):
        state = engine.run_tick(state, player_action=PlayerAction.wait())

        state.player_location = "술집"
    state.npc_locations["farmer"] = "술집"
    state = engine.run_tick(state, player_action=PlayerAction.talk("farmer"))

    assert state.day == 3
    assert state.time_phase == "낮"
    assert state.dialogues[-1].text == "오늘 날씨는 농사짓기 괜찮겠군."


