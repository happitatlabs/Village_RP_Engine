from __future__ import annotations

from collections import deque

from village_rp_engine.core.mode_controller import run_mode_tick
from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import create_initial_world_state
from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules
from village_rp_engine.logs.world_log import format_tick_summary, render_scene
from village_rp_engine.main import get_mode_display_label, prompt_player_action
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.player_action import PlayerAction


def build_engine() -> TickEngine:
    return TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=build_event_definitions(),
        seed=1,
    )


def test_observer_mode_runs_without_player_input() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    next_state = run_mode_tick(engine, state, Mode.OBSERVER)

    assert next_state.tick == 1
    assert next_state.time_phase == "낮"
    assert next_state.player_location == "광장"
    assert "플레이어 행동: 대기 (광장)" in next_state.world_log


def test_rp_mode_uses_player_action_path() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    next_state = run_mode_tick(
        engine,
        state,
        Mode.RP,
        action_provider=lambda: PlayerAction.move("술집"),
    )

    assert next_state.tick == 1
    assert next_state.player_location == "술집"
    assert "플레이어 행동: 이동 -> 술집" in next_state.world_log


def test_player_talk_does_not_advance_tick() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")
    state.tick = 3
    state.day = 2
    state.time_phase = "아침"
    state.npc_locations = {
        "blacksmith": "대장간",
        "farmer": "광장",
        "innkeeper": "술집",
        "village_elder": "광장",
        "guard_captain": "광장",
    }

    next_state = run_mode_tick(
        engine,
        state,
        Mode.RP,
        action_provider=lambda: PlayerAction.talk("village_elder"),
    )

    assert next_state.tick == 3
    assert next_state.day == 2
    assert next_state.time_phase == "아침"
    assert next_state.player_location == "광장"
    assert next_state.npc_locations == state.npc_locations
    assert next_state.dialogues[-1].speaker_id == "village_elder"
    assert "플레이어 행동: 대화 시도 -> village_elder" in next_state.world_log


def test_observer_mode_scene_text_is_neutral() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="술집")

    state = run_mode_tick(engine, state, Mode.OBSERVER)
    state = run_mode_tick(engine, state, Mode.OBSERVER)
    summary = format_tick_summary(state, mode=Mode.OBSERVER)

    assert "술집 안에서는 대장장이와 농부 사이에 팽팽한 말다툼이 벌어지고 있었다." in summary
    assert all("네가" not in render_scene(scene, Mode.OBSERVER) for scene in state.visible_scenes)


def test_rp_mode_scene_text_is_second_person() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda: PlayerAction.wait())
    state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda: PlayerAction.move("술집"))
    summary = format_tick_summary(state, mode=Mode.RP)

    assert "네가 술집에 발을 들이자, 대장장이와 농부가 서로를 향해 날 선 말을 주고받고 있었다." in summary


def test_observer_mode_hides_or_rewrites_player_action_log() -> None:
    engine = build_engine()
    state = create_initial_world_state(player_location="광장")

    state = run_mode_tick(engine, state, Mode.OBSERVER)
    summary = format_tick_summary(state, mode=Mode.OBSERVER)

    assert "플레이어 행동:" not in summary


def test_move_to_same_location_is_blocked() -> None:
    inputs = deque(["move 광장", "wait"])
    outputs: list[str] = []

    action = prompt_player_action(
        ["광장", "대장간", "술집"],
        ["blacksmith", "farmer", "innkeeper"],
        current_location="광장",
        input_func=lambda _: inputs.popleft(),
        output_func=outputs.append,
    )

    assert action == PlayerAction.wait()
    assert any("이미 광장에 있다." in line for line in outputs)


def test_move_alias_korean_normalized() -> None:
    inputs = deque(["이동 술집"])
    action = prompt_player_action(
        ["광장", "대장간", "술집"],
        ["blacksmith"],
        current_location="광장",
        input_func=lambda _: inputs.popleft(),
        output_func=lambda _: None,
    )
    assert action == PlayerAction.move("술집")

    inputs = deque(["술집 가기"])
    action = prompt_player_action(
        ["광장", "대장간", "술집"],
        ["blacksmith"],
        current_location="광장",
        input_func=lambda _: inputs.popleft(),
        output_func=lambda _: None,
    )
    assert action == PlayerAction.move("술집")


def test_talk_alias_korean_normalized() -> None:
    inputs = deque(["대화 대장장이"])
    action = prompt_player_action(
        ["광장", "대장간", "술집"],
        ["blacksmith"],
        current_location="광장",
        input_func=lambda _: inputs.popleft(),
        output_func=lambda _: None,
    )
    assert action == PlayerAction.talk("blacksmith")

    inputs = deque(["대장장이 말걸기"])
    action = prompt_player_action(
        ["광장", "대장간", "술집"],
        ["blacksmith"],
        current_location="광장",
        input_func=lambda _: inputs.popleft(),
        output_func=lambda _: None,
    )
    assert action == PlayerAction.talk("blacksmith")


def test_talk_alias_guard_captain_normalized() -> None:
    inputs = deque(["talk guard captain"])

    action = prompt_player_action(
        ["광장", "대장간", "술집"],
        ["guard_captain"],
        current_location="광장",
        input_func=lambda _: inputs.popleft(),
        output_func=lambda _: None,
    )

    assert action == PlayerAction.talk("guard_captain")

    inputs = deque(["경비대장 대화"])
    action = prompt_player_action(
        ["광장", "대장간", "술집"],
        ["guard_captain"],
        current_location="광장",
        input_func=lambda _: inputs.popleft(),
        output_func=lambda _: None,
    )

    assert action == PlayerAction.talk("guard_captain")


def test_talk_alias_village_elder_normalized() -> None:
    inputs = deque(["촌장 말걸기"])

    action = prompt_player_action(
        ["광장", "대장간", "술집"],
        ["village_elder"],
        current_location="광장",
        input_func=lambda _: inputs.popleft(),
        output_func=lambda _: None,
    )

    assert action == PlayerAction.talk("village_elder")

    inputs = deque(["대화 elder"])
    action = prompt_player_action(
        ["광장", "대장간", "술집"],
        ["village_elder"],
        current_location="광장",
        input_func=lambda _: inputs.popleft(),
        output_func=lambda _: None,
    )

    assert action == PlayerAction.talk("village_elder")


def test_alias_move_same_location_still_blocked() -> None:
    inputs = deque(["광장 가기", "대기"])
    outputs: list[str] = []

    action = prompt_player_action(
        ["광장", "대장간", "술집"],
        ["blacksmith"],
        current_location="광장",
        input_func=lambda _: inputs.popleft(),
        output_func=outputs.append,
    )

    assert action == PlayerAction.wait()
    assert any("이미 광장에 있다." in line for line in outputs)


def test_mode_header_uses_RP_label() -> None:
    assert get_mode_display_label(Mode.RP) == "RP"
