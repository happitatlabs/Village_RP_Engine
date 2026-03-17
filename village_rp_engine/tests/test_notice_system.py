from __future__ import annotations

from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules
from village_rp_engine.models.npc_state import NPCRecentState
from village_rp_engine.models.player_action import PlayerAction


def build_engine() -> TickEngine:
    return TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=[],
        seed=1,
    )


def test_common_notice_created_when_npc_and_player_share_location_at_dawn() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "밤"
    state.npc_locations = {
        "blacksmith": "집",
        "farmer": "집",
        "innkeeper": "술집",
        "village_elder": "집",
        "guard_captain": "광장",
    }

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.time_phase == "새벽"
    assert {(notice.observer_npc_id, notice.notice_type) for notice in state.player_notices} == {
        ("guard_captain", "noticed_player_at_dawn"),
    }
    assert state.visible_scenes[-1].text == "경비대장이 네 쪽을 한 번 훑어보았다."


def test_notice_does_not_create_immediate_dialogue() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "밤"
    state.npc_locations = {
        "blacksmith": "집",
        "farmer": "집",
        "innkeeper": "술집",
        "village_elder": "집",
        "guard_captain": "광장",
    }

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.time_phase == "새벽"
    assert state.player_notices
    assert state.dialogues == []
    assert state.visible_scenes[-1].text == "경비대장이 네 쪽을 한 번 훑어보았다."


def test_guard_captain_uses_notice_dialogue_on_talk() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "밤"
    state.npc_locations = {
        "blacksmith": "집",
        "farmer": "집",
        "innkeeper": "술집",
        "village_elder": "집",
        "guard_captain": "광장",
    }

    state = engine.run_tick(state, player_action=PlayerAction.talk("guard_captain"))

    assert state.time_phase == "새벽"
    assert state.dialogues[-1].speaker_id == "guard_captain"
    assert state.dialogues[-1].text == "이방인이 새벽에 돌아다니면 눈에 띄는 법이다."


def test_village_elder_uses_notice_dialogue_on_talk() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="집")
    state.time_phase = "밤"
    state.npc_locations = {
        "blacksmith": "집",
        "farmer": "집",
        "innkeeper": "술집",
        "village_elder": "집",
        "guard_captain": "광장",
    }

    state = engine.run_tick(state, player_action=PlayerAction.talk("village_elder"))

    assert state.time_phase == "새벽"
    assert state.dialogues[-1].speaker_id == "village_elder"
    assert state.dialogues[-1].text == "새벽부터 움직이는군. 무슨 일이라도 있나?"


def test_notice_expires_or_is_ignored_after_lifetime() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "밤"
    state.npc_locations = {
        "blacksmith": "집",
        "farmer": "집",
        "innkeeper": "술집",
        "village_elder": "집",
        "guard_captain": "광장",
    }

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    assert state.player_notices

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    assert state.time_phase == "아침"
    assert state.player_notices == []

    state.npc_locations["guard_captain"] = "광장"
    state = engine.run_tick(state, player_action=PlayerAction.talk("guard_captain"))

    assert state.dialogues[-1].text == "광장은 늘 눈여겨봐야 하는 자리다."


def test_notice_priority_is_below_recent_state() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "밤"
    state.npc_locations = {
        "blacksmith": "집",
        "farmer": "집",
        "innkeeper": "술집",
        "village_elder": "집",
        "guard_captain": "광장",
    }
    state.npc_recent_states = {
        "guard_captain": [
            NPCRecentState(
                npc_id="guard_captain",
                state_id="watchful_after_tavern_argument",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ]
    }

    state = engine.run_tick(state, player_action=PlayerAction.talk("guard_captain"))

    assert state.dialogues[-1].text == "또 소란이 생기면 이번엔 그냥 넘기지 않겠다."
