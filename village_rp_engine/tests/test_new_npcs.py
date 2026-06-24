from __future__ import annotations

from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules
from village_rp_engine.models.player_action import PlayerAction


def build_engine(event_definitions=None) -> TickEngine:
    return TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=build_event_definitions() if event_definitions is None else event_definitions,
        seed=1,
    )


def test_new_npcs_are_in_npc_registry() -> None:
    npcs = build_npcs()
    npc_ids = [npc.npc_id for npc in npcs]
    influences = {npc.npc_id: npc.influence for npc in npcs}

    assert "village_elder" in npc_ids
    assert "guard_captain" in npc_ids
    assert "ethan" in npc_ids
    assert influences["village_elder"] == "high"
    assert influences["guard_captain"] == "high"
    assert influences["ethan"] == "medium"


def test_new_npcs_have_schedules() -> None:
    schedules = build_schedules()

    assert schedules["village_elder"] == {
        "아침": "광장",
        "낮": "광장",
        "저녁": "술집",
        "밤": "집",
        "새벽": "집",
    }
    assert schedules["guard_captain"] == {
        "아침": "광장",
        "낮": "광장",
        "저녁": "술집",
        "밤": "광장",
        "새벽": "광장",
    }
    assert schedules["ethan"] == {
        "아침": "광장",
        "낮": "광장",
        "저녁": "술집",
        "밤": "집",
        "새벽": "집",
    }


def test_talk_to_village_elder_returns_dialogue() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.talk("village_elder"))

    assert len(state.dialogues) == 1
    assert state.dialogues[0].speaker_id == "village_elder"
    assert state.dialogues[0].speaker_name == "촌장"


def test_talk_to_guard_captain_returns_dialogue() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.talk("guard_captain"))

    assert len(state.dialogues) == 1
    assert state.dialogues[0].speaker_id == "guard_captain"
    assert state.dialogues[0].speaker_name == "경비대장"


def test_talk_to_ethan_returns_dialogue() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.talk("ethan"))

    assert len(state.dialogues) == 1
    assert state.dialogues[0].speaker_id == "ethan"
    assert state.dialogues[0].speaker_name == "에단"


def test_new_npcs_can_appear_in_idle_or_arrival_scene() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.move("광장"))

    assert state.time_phase == "밤"
    assert len(state.visible_scenes) == 1
    assert "경비대장" in state.visible_scenes[0].text or "경비대장" in state.visible_scenes[0].observer_text
