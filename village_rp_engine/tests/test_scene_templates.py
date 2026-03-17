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


def test_event_scene_uses_entry_text_when_player_moved() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")
    state.time_phase = "새벽"

    state = engine.run_tick(state, player_action=PlayerAction.move("광장"))

    assert state.visible_scenes[0].text == "네가 광장에 이르렀을 때, 농부는 사람들과 아침 공기 속에서 한가로운 이야기를 나누고 있었다."


def test_event_scene_uses_observe_text_when_player_waited() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "새벽"

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.visible_scenes[0].text == "광장에서는 농부가 사람들 사이에 섞여 느긋한 아침 이야기를 이어가고 있었다."


def test_event_scene_uses_neutral_template_in_observer_mode() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.move("술집"))

    assert "술집 안에서는 대장장이와 농부 사이에 팽팽한 말다툼이 벌어지고 있었다." == state.visible_scenes[0].observer_text


def test_idle_scene_still_uses_entry_style_text() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.move("술집"))

    assert "네가 술집 안을 둘러보자, 여관주인이 잔을 닦으며 손님 맞을 준비를 하고 있었다." == state.visible_scenes[0].text


def test_template_selection_is_deterministic() -> None:
    engine_one = build_engine()
    engine_two = build_engine()
    state_one = create_initial_world_state(player_location="술집")
    state_two = create_initial_world_state(player_location="술집")
    state_one.time_phase = "새벽"
    state_two.time_phase = "새벽"

    state_one = engine_one.run_tick(state_one, player_action=PlayerAction.move("광장"))
    state_two = engine_two.run_tick(state_two, player_action=PlayerAction.move("광장"))

    assert state_one.visible_scenes[0].text == state_two.visible_scenes[0].text
    assert state_one.visible_scenes[0].observer_text == state_two.visible_scenes[0].observer_text

def test_guard_captain_scene_not_relaxed() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")
    state.time_phase = "밤"

    state = engine.run_tick(state, player_action=PlayerAction.move("광장"))

    assert "경비대장" in state.visible_scenes[0].text
    assert "느긋" not in state.visible_scenes[0].text
    assert "한가로운" not in state.visible_scenes[0].text
