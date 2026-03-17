from __future__ import annotations

from run_demo import DEFAULT_DEMO_TICKS
from village_rp_engine.core.mode_controller import build_engine, create_default_state, run_mode_tick
from village_rp_engine.demo import (
    DemoActionProvider,
    ELDER_MEDIATION_DEMO_DESCRIPTION,
    FLOW_DEMO_DESCRIPTION,
    GUARD_DAWN_DEMO_DESCRIPTION,
    build_demo_actions,
    build_elder_mediation_demo_actions,
    build_guard_dawn_demo_actions,
    create_elder_mediation_demo_state,
    create_guard_dawn_demo_state,
    format_action,
    parse_demo_action,
)
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.player_action import PlayerAction


def test_parse_demo_action_supports_move_talk_and_wait() -> None:
    assert parse_demo_action("wait") == PlayerAction.wait()
    assert parse_demo_action("move 술집") == PlayerAction.move("술집")
    assert parse_demo_action("talk innkeeper") == PlayerAction.talk("innkeeper")
    assert parse_demo_action("talk guard captain") == PlayerAction.talk("guard_captain")
    assert parse_demo_action("talk 경비대장") == PlayerAction.talk("guard_captain")
    assert parse_demo_action("talk village elder") == PlayerAction.talk("village_elder")


def test_demo_action_provider_falls_back_to_wait_after_script() -> None:
    provider = DemoActionProvider(build_demo_actions(["move 대장간", "talk blacksmith"]))

    assert provider.next_action() == PlayerAction.move("대장간")
    assert provider.next_action() == PlayerAction.talk("blacksmith")
    assert provider.next_action() == PlayerAction.wait()


def test_format_action_returns_cli_style_text() -> None:
    assert format_action(PlayerAction.move("광장")) == "move 광장"
    assert format_action(PlayerAction.talk("farmer")) == "talk farmer"
    assert format_action(PlayerAction.wait()) == "wait"


def test_run_demo_uses_twenty_ticks_by_default() -> None:
    assert DEFAULT_DEMO_TICKS == 20


def test_demo_descriptions_explain_verification_mode() -> None:
    assert FLOW_DEMO_DESCRIPTION.startswith("이 데모는 실제 흐름")
    assert GUARD_DAWN_DEMO_DESCRIPTION.startswith("주의: 이 데모는")
    assert ELDER_MEDIATION_DEMO_DESCRIPTION.startswith("주의: 이 데모는")


def test_default_demo_reaches_guard_captain_dawn_talk() -> None:
    actions = build_demo_actions()

    assert actions[-1] == PlayerAction.talk("guard_captain")


def test_default_demo_triggers_guard_captain_dawn_dialogue() -> None:
    engine = build_engine()
    state = create_default_state()

    for action in build_demo_actions():
        state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda action=action: action)

    assert state.time_phase == "새벽"
    assert state.tick == 4
    assert state.dialogues[-1].speaker_id == "guard_captain"
    assert state.dialogues[-1].text == "이방인이 새벽에 돌아다니면 눈에 띄는 법이다."


def test_guard_dawn_demo_triggers_guard_dialogue() -> None:
    engine = build_engine()
    state = create_guard_dawn_demo_state()

    for action in build_guard_dawn_demo_actions():
        state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda action=action: action)

    assert state.time_phase == "새벽"
    assert state.tick == 1
    assert state.dialogues[-1].speaker_id == "guard_captain"
    assert state.dialogues[-1].text == "이방인이 새벽에 돌아다니면 눈에 띄는 법이다."


def test_elder_mediation_demo_triggers_indirect_dialogue() -> None:
    engine = build_engine()
    state = create_elder_mediation_demo_state()

    for action in build_elder_mediation_demo_actions():
        state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda action=action: action)

    assert state.dialogues[-1].speaker_id == "village_elder"
    assert state.dialogues[-1].text == "작은 다툼도 오래 두면 마을 분위기를 흐리네."
