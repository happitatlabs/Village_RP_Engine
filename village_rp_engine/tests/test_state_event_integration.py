from __future__ import annotations

from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules
from village_rp_engine.models.event import EventDefinition
from village_rp_engine.models.npc_state import NPCRecentState
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.models.rumor import Rumor


def build_engine(event_definitions: list[EventDefinition] | None = None) -> TickEngine:
    return TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=event_definitions or build_event_definitions(),
        seed=1,
    )


def test_farmer_state_changes_evening_movement() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "낮"
    state.npc_locations = {
        "blacksmith": "대장간",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "광장",
        "guard_captain": "광장",
    }
    state.npc_recent_states = {
        "farmer": [
            NPCRecentState(
                npc_id="farmer",
                state_id="complaining_about_blacksmith",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ]
    }

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.time_phase == "저녁"
    assert state.npc_locations["farmer"] == "광장"


def test_blacksmith_state_changes_evening_movement() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "낮"
    state.npc_locations = {
        "blacksmith": "대장간",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "광장",
        "guard_captain": "광장",
    }
    state.npc_recent_states = {
        "blacksmith": [
            NPCRecentState(
                npc_id="blacksmith",
                state_id="irritated_with_farmer",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ]
    }

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.time_phase == "저녁"
    assert state.npc_locations["blacksmith"] == "대장간"


def test_argument_event_is_blocked_by_recent_state_movement_overrides() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "낮"
    state.npc_locations = {
        "blacksmith": "대장간",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "광장",
        "guard_captain": "광장",
    }
    state.npc_recent_states = {
        "blacksmith": [
            NPCRecentState(
                npc_id="blacksmith",
                state_id="irritated_with_farmer",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ],
        "farmer": [
            NPCRecentState(
                npc_id="farmer",
                state_id="complaining_about_blacksmith",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ],
    }

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.time_phase == "저녁"
    assert state.npc_locations["blacksmith"] == "대장간"
    assert state.npc_locations["farmer"] == "광장"
    assert [event.event_id for event in state.triggered_events] == []


def test_farmer_grumbling_square_replaces_morning_chat_square() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "새벽"
    state.day = 2
    state.npc_locations = {
        "blacksmith": "집",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "집",
        "guard_captain": "광장",
    }
    state.npc_recent_states = {
        "farmer": [
            NPCRecentState(
                npc_id="farmer",
                state_id="complaining_about_blacksmith",
                source_event_id="argument_at_tavern",
                expires_day=3,
            )
        ]
    }

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert [event.event_id for event in state.triggered_events] == ["farmer_grumbling_square"]


def test_morning_chat_square_returns_without_farmer_state() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "새벽"
    state.day = 2
    state.npc_locations = {
        "blacksmith": "집",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "집",
        "guard_captain": "광장",
    }

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert [event.event_id for event in state.triggered_events] == ["morning_chat_square"]


def test_guard_state_assigned_only_when_hidden_argument_creates_rumor() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())

    guard_state_ids = {npc_state.state_id for npc_state in state.npc_recent_states.get("guard_captain", [])}

    assert "argument_at_tavern" in [rumor.source_event_id for rumor in state.rumor_log]
    assert "watchful_after_tavern_argument" in guard_state_ids


def test_guard_state_not_assigned_when_argument_visible() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())

    guard_state_ids = {npc_state.state_id for npc_state in state.npc_recent_states.get("guard_captain", [])}

    assert "watchful_after_tavern_argument" not in guard_state_ids


def test_guard_state_not_assigned_when_hidden_argument_creates_no_rumor() -> None:
    event_definitions = [
        EventDefinition(
            event_id="argument_at_tavern",
            time_phase="저녁",
            location="술집",
            required_actor_ids=("blacksmith", "farmer"),
            outcome_text="대장장이와 농부가 술집에서 말다툼을 벌였다.",
            rumor_text="술집에서 대장장이와 농부가 언성을 높였다는 소문이 퍼졌다.",
            narration_text="",
            observer_narration_text="",
            probability=1.0,
            cooldown_tick=2,
            rumor_base_score=1,
        )
    ]
    engine = build_engine(event_definitions)
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "낮"
    state.npc_locations = {
        "blacksmith": "대장간",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "광장",
        "guard_captain": "광장",
    }

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    guard_state_ids = {npc_state.state_id for npc_state in state.npc_recent_states.get("guard_captain", [])}

    assert [event.event_id for event in state.triggered_events] == ["argument_at_tavern"]
    assert state.rumor_log == []
    assert "watchful_after_tavern_argument" not in guard_state_ids


def test_watchful_guard_moves_to_tavern_at_night() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "저녁"
    state.npc_locations = {
        "blacksmith": "술집",
        "farmer": "술집",
        "innkeeper": "술집",
        "village_elder": "술집",
        "guard_captain": "술집",
    }
    state.npc_recent_states = {
        "guard_captain": [
            NPCRecentState(
                npc_id="guard_captain",
                state_id="watchful_after_tavern_argument",
                source_event_id="argument_at_tavern",
                expires_day=3,
            )
        ]
    }

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.time_phase == "밤"
    assert state.npc_locations["guard_captain"] == "술집"


def test_village_elder_uses_indirect_farmer_state_dialogue() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "아침"
    state.npc_locations = {
        "blacksmith": "대장간",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "광장",
        "guard_captain": "광장",
    }
    state.npc_recent_states = {
        "farmer": [
            NPCRecentState(
                npc_id="farmer",
                state_id="complaining_about_blacksmith",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ]
    }

    state = engine.run_tick(state, player_action=PlayerAction.talk("village_elder"))

    assert state.dialogues[-1].text == "농부 쪽에 아직 감정이 남아 있는 모양이군."


def test_village_elder_recent_state_still_has_priority_over_indirect_reaction() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "아침"
    state.npc_locations = {
        "blacksmith": "대장간",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "광장",
        "guard_captain": "광장",
    }
    state.npc_recent_states = {
        "village_elder": [
            NPCRecentState(
                npc_id="village_elder",
                state_id="concerned_about_tavern_argument",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ],
        "farmer": [
            NPCRecentState(
                npc_id="farmer",
                state_id="complaining_about_blacksmith",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ],
    }

    state = engine.run_tick(state, player_action=PlayerAction.talk("village_elder"))

    assert state.dialogues[-1].text == "어젯밤 소란은 그냥 넘길 일이 아니네."


def test_village_elder_falls_back_to_normal_dialogue_without_farmer_state() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "아침"
    state.npc_locations = {
        "blacksmith": "대장간",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "광장",
        "guard_captain": "광장",
    }
    state.rumor_log = [
        Rumor(
            source_event_id="argument_at_tavern",
            tick=2,
            day=1,
            time_phase="저녁",
            location="광장",
            text="광장에서도 술집 소란 이야기가 돌고 있다.",
        )
    ]

    state = engine.run_tick(state, player_action=PlayerAction.talk("village_elder"))

    assert state.dialogues[-1].text == "사람들 입에 오르내리는 일은 빨리 정리해야 하네."


def test_village_elder_indirect_dialogue_is_distinct_from_direct_state_dialogue() -> None:
    engine = build_engine([])
    base_locations = {
        "blacksmith": "대장간",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "광장",
        "guard_captain": "광장",
    }

    indirect_state = create_initial_world_state(player_location="광장")
    indirect_state.time_phase = "아침"
    indirect_state.npc_locations = dict(base_locations)
    indirect_state.npc_recent_states = {
        "farmer": [
            NPCRecentState(
                npc_id="farmer",
                state_id="complaining_about_blacksmith",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ]
    }
    indirect_state = engine.run_tick(indirect_state, player_action=PlayerAction.talk("village_elder"))

    direct_state = create_initial_world_state(player_location="광장")
    direct_state.time_phase = "아침"
    direct_state.npc_locations = dict(base_locations)
    direct_state.npc_recent_states = {
        "village_elder": [
            NPCRecentState(
                npc_id="village_elder",
                state_id="concerned_about_tavern_argument",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ]
    }
    direct_state = engine.run_tick(direct_state, player_action=PlayerAction.talk("village_elder"))

    assert indirect_state.dialogues[-1].text != direct_state.dialogues[-1].text
