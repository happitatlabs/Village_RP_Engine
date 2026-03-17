from __future__ import annotations

from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules
from village_rp_engine.models.event import EventDefinition
from village_rp_engine.models.player_action import PlayerAction


def build_engine(event_definitions: list[EventDefinition] | None = None) -> TickEngine:
    return TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=event_definitions if event_definitions is not None else build_event_definitions(),
        seed=1,
    )


def test_scene_generated_when_event_visible() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.move("술집"))

    assert [scene.source_event_id for scene in state.visible_scenes] == ["argument_at_tavern"]
    assert "네가 술집에 발을 들이자, 대장장이와 농부가 서로를 향해 날 선 말을 주고받고 있었다." == state.visible_scenes[0].text
    assert "술집 안에서는 대장장이와 농부 사이에 팽팽한 말다툼이 벌어지고 있었다." == state.visible_scenes[0].observer_text


def test_scene_not_repeated_each_tick() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.move("술집"))
    first_scene_ids = [scene.source_event_id for scene in state.visible_scenes]

    state = engine.run_tick(state, player_action=PlayerAction.move("대장간"))
    second_scene_ids = [scene.source_event_id for scene in state.visible_scenes]

    assert first_scene_ids == ["argument_at_tavern"]
    assert "argument_at_tavern" not in second_scene_ids


def test_idle_scene_on_location_entry() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.move("대장간"))

    assert len(state.visible_scenes) == 1
    assert state.visible_scenes[0].source_event_id is None
    assert "네가 대장간에 들어서자, 대장장이가 작업대를 살피며 하루 일을 준비하고 있었다." == state.visible_scenes[0].text
    assert "대장간에서는 대장장이가 작업대를 살피며 하루 일을 준비하고 있었다." == state.visible_scenes[0].observer_text


def test_no_idle_scene_when_player_stays() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.move("대장간"))
    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.player_location == "대장간"
    assert state.visible_scenes == []


def test_bootstrap_tick_does_not_generate_arrival_scene() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.visible_scenes == []


def test_arrival_scene_still_generated_on_real_later_entry() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert len(state.visible_scenes) == 1
    assert state.visible_scenes[0].source_event_id is None
    assert state.visible_scenes[0].text in {
        "잠시 뒤 대장장이가 술집 안으로 들어와 주변을 훑어보았다.",
        "잠시 뒤 경비대장이 술집 안으로 들어서며 주변을 재빨리 살폈다.",
    }


def test_arrival_scene_not_generated_when_npc_was_already_present() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert [scene.source_event_id for scene in state.visible_scenes] == ["argument_at_tavern"]


def test_event_scene_has_priority_over_arrival_scene() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.visible_scenes[0].source_event_id == "argument_at_tavern"

