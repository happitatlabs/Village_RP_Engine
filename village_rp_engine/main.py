from __future__ import annotations

import argparse
from collections.abc import Callable

from village_rp_engine.config import DEFAULT_SIMULATION_TICKS
from village_rp_engine.core.mode_controller import build_engine, create_default_state, run_mode_tick
from village_rp_engine.domain.location_data import build_locations
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.input_aliases import parse_player_input
from village_rp_engine.logs.world_log import format_tick_summary
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.player_action import PlayerAction


MODE_DISPLAY_LABELS = {
    Mode.RP: "RP",
    Mode.OBSERVER: "Observer",
}


def run_simulation(ticks: int = DEFAULT_SIMULATION_TICKS, mode: Mode = Mode.RP) -> None:
    state = create_default_state()
    locations = [location for location in build_locations() if location != "집"]
    npc_ids = [npc.npc_id for npc in build_npcs()]
    engine = build_engine()

    print(f"=== Village RP Engine | {get_mode_display_label(mode)} Mode ===")
    print(f"초기 플레이어 위치: {state.player_location}")
    print()

    for _ in range(ticks):
        action_provider = (
            lambda current_state=state: prompt_player_action(locations, npc_ids, current_state.player_location)
        ) if mode == Mode.RP else None
        state = run_mode_tick(engine, state, mode, action_provider=action_provider)
        print(format_tick_summary(state, mode=mode))
        print()


def get_mode_display_label(mode: Mode) -> str:
    return MODE_DISPLAY_LABELS[mode]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Village RP Engine")
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in Mode],
        default=Mode.RP.value,
        help="실행 모드 선택: observer 또는 rp",
    )
    parser.add_argument(
        "--ticks",
        type=int,
        default=DEFAULT_SIMULATION_TICKS,
        help="실행할 tick 수",
    )
    return parser.parse_args()


def prompt_player_action(
    locations: list[str],
    npc_ids: list[str],
    current_location: str,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> PlayerAction:
    location_text = ", ".join(locations)
    npc_text = ", ".join(npc_ids)
    output_func(
        "행동 선택: `wait`, `move <장소>`, `talk <대상>` "
        f"(예: `이동 술집`, `술집 가기`, `대화 대장장이`, `촌장 말걸기`) ({location_text} | {npc_text})"
    )
    while True:
        try:
            raw = input_func("> ")
        except EOFError:
            return PlayerAction.wait()

        action = parse_player_input(raw)
        if action is None:
            output_func("지원하지 않는 행동입니다. `wait`, `move <장소>`, `talk <대상>` 형식으로 입력하세요.")
            continue

        if action.action_type == "move" and action.target_location:
            destination = action.target_location
            if destination == current_location:
                output_func(f"이미 {current_location}에 있다.")
                continue
            if destination in locations:
                return action
            output_func(f"이동할 수 없는 장소입니다. 가능한 장소: {location_text}")
            continue

        if action.action_type == "talk" and action.target_npc_id:
            return action

        if action.action_type == "wait":
            return action

        output_func("지원하지 않는 행동입니다. `wait`, `move <장소>`, `talk <대상>` 형식으로 입력하세요.")


if __name__ == "__main__":
    args = parse_args()
    run_simulation(ticks=args.ticks, mode=Mode(args.mode))
