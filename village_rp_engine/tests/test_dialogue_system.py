from __future__ import annotations

from village_rp_engine.core.mode_controller import run_mode_tick
from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules
from village_rp_engine.logs.world_log import format_tick_summary
from village_rp_engine.models.event import TriggeredEvent
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.npc_state import NPCRecentState
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.models.rumor import Rumor


def build_engine(event_definitions=None) -> TickEngine:
    return TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=build_event_definitions() if event_definitions is None else event_definitions,
        seed=1,
    )


def test_talk_action_returns_dialogue_for_npc_in_same_location() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.talk("innkeeper"))

    assert len(state.dialogues) == 1
    assert state.dialogues[0].speaker_id == "innkeeper"
    assert state.dialogues[0].speaker_name == "여관주인"
    assert state.dialogues[0].source_type == "talk"


def test_talk_action_fails_for_npc_not_in_same_location() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.talk("blacksmith"))

    assert state.dialogues == []
    assert "대화 실패: 그 인물은 이곳에 없다." in state.world_log


def test_dialogue_uses_rumor_when_available() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="술집")
    state.rumor_log = [
        Rumor(
            source_event_id="argument_at_tavern",
            tick=2,
            day=1,
            time_phase="저녁",
            location="술집",
            text="술집에서 대장장이와 농부가 언성을 높였다는 소문이 퍼졌다.",
        )
    ]

    state = engine.run_tick(state, player_action=PlayerAction.talk("innkeeper"))

    assert len(state.dialogues) == 1
    assert state.dialogues[0].text == "어젯밤 일은 다들 한마디씩 얹고 가더군."


def test_talk_action_consumes_tick() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.talk("innkeeper"))

    assert state.tick == 1
    assert state.time_phase == "낮"


def test_talk_uses_pre_move_npc_location() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="대장간")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.talk("blacksmith"))

    assert state.tick == 2
    assert state.time_phase == "저녁"
    assert len(state.dialogues) == 1
    assert state.dialogues[0].speaker_id == "blacksmith"
    assert state.npc_locations["blacksmith"] == "대장간"


def test_talk_failure_uses_pre_move_state() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.talk("blacksmith"))

    assert state.tick == 2
    assert state.dialogues == []
    assert "대화 실패: 그 인물은 이곳에 없다." in state.world_log


def test_successful_talk_does_not_show_arrival_scene_same_tick() -> None:
    engine = TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=[],
        seed=1,
    )
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.talk("innkeeper"))

    assert len(state.dialogues) == 1
    assert state.visible_scenes == []


def test_event_dialogue_priority() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.talk("innkeeper"))

    assert state.dialogues[-1].text == "오늘도 조용히 넘어가진 않겠네."


def test_rumor_dialogue_priority() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="술집")
    state.rumor_log = [
        Rumor(
            source_event_id="argument_at_tavern",
            tick=2,
            day=1,
            time_phase="저녁",
            location="술집",
            text="술집에서 대장장이와 농부가 언성을 높였다는 소문이 퍼졌다.",
        )
    ]

    state = engine.run_tick(state, player_action=PlayerAction.talk("innkeeper"))

    assert state.dialogues[0].text == "어젯밤 일은 다들 한마디씩 얹고 가더군."


def test_location_dialogue_priority() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.talk("innkeeper"))

    assert state.dialogues[0].text == "여긴 저녁만 되면 시끄러워지지."


def test_time_dialogue_priority() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.talk("blacksmith"))

    assert state.time_phase == "밤"
    assert state.dialogues[0].text == "밤공기가 차가워지면 쇠도 다르게 울리지."


def test_default_dialogue_fallback() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="술집")
    state.time_phase = "낮"
    state.npc_locations = {
        "blacksmith": "술집",
        "farmer": "광장",
        "innkeeper": "술집",
    }

    state = engine.run_tick(state, player_action=PlayerAction.talk("blacksmith"))

    assert state.time_phase == "저녁"
    assert state.dialogues[0].text == "쓸 만한 연장은 손에 익어야 해."


def test_visible_event_generates_overheard_dialogue_in_rp_mode() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())
    summary = format_tick_summary(state, mode=Mode.RP)

    assert any(dialogue.source_type == "event" for dialogue in state.dialogues)
    assert '대장장이: "괜한 말이 너무 많아."' in summary
    assert '농부: "대장장이랑은 한동안 말 섞기 싫어."' in summary


def test_visible_event_generates_overheard_dialogue_in_observer_mode() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = run_mode_tick(engine, state, Mode.OBSERVER)
    state = run_mode_tick(engine, state, Mode.OBSERVER)
    summary = format_tick_summary(state, mode=Mode.OBSERVER)

    assert any(dialogue.source_type == "event" for dialogue in state.dialogues)
    assert '대장장이: "괜한 말이 너무 많아."' in summary


def test_non_visible_event_does_not_generate_overheard_dialogue() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.triggered_events
    assert all(dialogue.source_type != "event" for dialogue in state.dialogues)


def test_event_dialogue_and_talk_dialogue_can_coexist() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.talk("innkeeper"))

    assert [dialogue.source_type for dialogue in state.dialogues] == ["event", "event", "talk"]
    assert state.dialogues[-1].speaker_id == "innkeeper"


def test_event_dialogue_selection_is_deterministic() -> None:
    engine_one = build_engine()
    engine_two = build_engine()
    state_one = create_initial_world_state(player_location="술집")
    state_two = create_initial_world_state(player_location="술집")

    state_one = engine_one.run_tick(state_one, player_action=PlayerAction.wait())
    state_one = engine_one.run_tick(state_one, player_action=PlayerAction.wait())

    state_two = engine_two.run_tick(state_two, player_action=PlayerAction.wait())
    state_two = engine_two.run_tick(state_two, player_action=PlayerAction.wait())

    assert [dialogue.text for dialogue in state_one.dialogues] == [dialogue.text for dialogue in state_two.dialogues]


def test_talk_locks_npc_movement() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="대장간")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.talk("blacksmith"))

    assert "blacksmith" in state.locked_npc_ids_for_tick
    assert state.npc_locations["blacksmith"] == "대장간"


def test_other_npcs_still_move_when_one_is_locked() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="대장간")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.talk("blacksmith"))

    assert state.npc_locations["blacksmith"] == "대장간"
    assert state.npc_locations["farmer"] == "술집"


def test_lock_applies_only_for_single_tick() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="대장간")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.talk("blacksmith"))
    assert state.npc_locations["blacksmith"] == "대장간"

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert state.locked_npc_ids_for_tick == set()
    assert state.npc_locations["blacksmith"] == "집"


def test_locked_npc_prevents_event_trigger() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="대장간")

    state = engine.run_tick(state, player_action=PlayerAction.wait())
    state = engine.run_tick(state, player_action=PlayerAction.talk("blacksmith"))

    assert state.time_phase == "저녁"
    assert state.npc_locations["blacksmith"] == "대장간"
    assert state.npc_locations["farmer"] == "술집"
    assert [event.event_id for event in state.triggered_events] == []


def test_recent_state_overrides_event_overheard_dialogue() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "새벽"
    state.day = 2
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
    assert [dialogue.text for dialogue in state.dialogues] == ["어젯밤 일은 아직도 기분이 나쁘군."]


def test_event_overheard_dialogue_falls_back_when_no_recent_state() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "새벽"
    state.day = 2

    state = engine.run_tick(state, player_action=PlayerAction.wait())

    assert [event.event_id for event in state.triggered_events] == ["morning_chat_square"]
    assert [dialogue.text for dialogue in state.dialogues] == ["오늘 아침 공기는 괜찮군."]


def test_multiple_event_speakers_can_use_their_own_recent_states() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="술집")
    state.tick = 2
    state.time_phase = "저녁"
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

    dialogues = engine.dialogue_system.create_event_dialogues(
        state,
        [
            TriggeredEvent(
                event_id="argument_at_tavern",
                time_phase="저녁",
                location="술집",
                actor_ids=("blacksmith", "farmer"),
                outcome_text="",
                rumor_text="",
                narration_text="",
                observer_narration_text="",
                rumor_base_score=2,
                witnessed=True,
            )
        ],
    )

    assert [dialogue.text for dialogue in dialogues] == [
        "괜한 말이 너무 많아.",
        "대장장이랑은 한동안 말 섞기 싫어.",
    ]


def test_recent_state_event_dialogue_respects_expiration() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "새벽"
    state.day = 2
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

    assert [event.event_id for event in state.triggered_events] == ["morning_chat_square"]
    assert [dialogue.text for dialogue in state.dialogues] == ["오늘 아침 공기는 괜찮군."]


def test_village_elder_uses_concerned_state_dialogue() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "아침"
    state.npc_locations = {
        "village_elder": "광장",
        "guard_captain": "광장",
        "blacksmith": "대장간",
        "farmer": "광장",
        "innkeeper": "술집",
    }
    state.npc_recent_states = {
        "village_elder": [
            NPCRecentState(
                npc_id="village_elder",
                state_id="concerned_about_tavern_argument",
                source_event_id="argument_at_tavern",
                expires_day=2,
            )
        ]
    }

    state = engine.run_tick(state, player_action=PlayerAction.talk("village_elder"))

    assert state.dialogues[-1].text == "어젯밤 소란은 그냥 넘길 일이 아니네."


def test_guard_captain_uses_watchful_state_dialogue() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "아침"
    state.npc_locations = {
        "village_elder": "광장",
        "guard_captain": "광장",
        "blacksmith": "대장간",
        "farmer": "광장",
        "innkeeper": "술집",
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


def test_guard_captain_uses_dawn_notice_dialogue_without_recent_state() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "밤"
    state.npc_locations = {
        "village_elder": "집",
        "guard_captain": "광장",
        "blacksmith": "집",
        "farmer": "집",
        "innkeeper": "술집",
    }

    state = engine.run_tick(state, player_action=PlayerAction.talk("guard_captain"))

    assert state.time_phase == "새벽"
    assert state.dialogues[-1].text == "이방인이 새벽에 돌아다니면 눈에 띄는 법이다."


def test_guard_captain_normal_time_uses_recent_state() -> None:
    engine = build_engine([])
    state = create_initial_world_state(player_location="광장")
    state.time_phase = "아침"
    state.npc_locations = {
        "village_elder": "광장",
        "guard_captain": "광장",
        "blacksmith": "대장간",
        "farmer": "광장",
        "innkeeper": "술집",
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

    assert state.time_phase == "낮"
    assert state.dialogues[-1].text == "또 소란이 생기면 이번엔 그냥 넘기지 않겠다."
