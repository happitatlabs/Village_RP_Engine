from __future__ import annotations

import argparse
from collections import deque
from collections.abc import Callable

from village_rp_engine.config import DEFAULT_SIMULATION_TICKS
from village_rp_engine.core.mode_controller import build_world_engine, create_default_world_snapshot, run_mode_step
from village_rp_engine.core.world_engine import can_travel_between_settlements
from village_rp_engine.input_aliases import parse_player_input
from village_rp_engine.logs.world_log import format_tick_summary
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.player_action import PlayerAction


MODE_DISPLAY_LABELS = {
    Mode.RP: 'RP',
    Mode.OBSERVER: 'Observer',
}


def run_simulation(ticks: int = DEFAULT_SIMULATION_TICKS, mode: Mode = Mode.RP) -> None:
    snapshot = create_default_world_snapshot()
    world_engine = build_world_engine()

    print(f'=== Village RP Engine | {get_mode_display_label(mode)} Mode ===')
    print(f'초기 정착지: {snapshot.active_settlement_id}')
    print(f'초기 플레이어 위치: {snapshot.settlement_state.player_location}')
    print()

    for _ in range(ticks):
        settlement_definition = snapshot.settlement_definition
        locations = [location for location in settlement_definition.locations if location != '집']
        npc_ids = list(settlement_definition.npc_ids)
        travel_targets = [
            settlement_id
            for settlement_id in snapshot.settlement_definitions
            if can_travel_between_settlements(snapshot.active_settlement_id, settlement_id, snapshot.settlement_links)
        ]
        action_provider = (
            lambda current_state=snapshot.settlement_state: prompt_player_action(
                locations,
                npc_ids,
                current_location=current_state.player_location,
                travel_targets=travel_targets,
            )
        ) if mode == Mode.RP else None
        snapshot = run_mode_step(world_engine, snapshot, mode, action_provider=action_provider)
        print(f'[Settlement] {snapshot.active_settlement_id}')
        print(format_tick_summary(snapshot.settlement_state, mode=mode))
        print()


def get_mode_display_label(mode: Mode) -> str:
    return MODE_DISPLAY_LABELS[mode]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Village RP Engine')
    parser.add_argument(
        '--mode',
        choices=[mode.value for mode in Mode],
        default=Mode.RP.value,
        help='실행 모드 선택: observer 또는 rp',
    )
    parser.add_argument(
        '--ticks',
        type=int,
        default=DEFAULT_SIMULATION_TICKS,
        help='실행할 tick 수',
    )
    return parser.parse_args()


def prompt_player_action(
    locations: list[str],
    npc_ids: list[str],
    current_location: str | None,
    travel_targets: list[str] | None = None,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> PlayerAction:
    location_text = ', '.join(locations)
    npc_text = ', '.join(npc_ids)
    travel_text = ', '.join(travel_targets or [])
    output_func(
        '행동 선택: `wait`, `move <장소>`, `talk <대상>`, `travel <settlement>` '
        f'(예: `이동 술집`, `대화 대장장이`, `travel village_2`) ({location_text} | {npc_text} | {travel_text})'
    )
    while True:
        try:
            raw = input_func('> ')
        except EOFError:
            return PlayerAction.wait()

        action = parse_player_input(raw)
        if action is None:
            output_func('지원하지 않는 행동입니다. `wait`, `move <장소>`, `talk <대상>`, `travel <settlement>` 형식으로 입력하세요.')
            continue

        if action.action_type == 'move' and action.target_location:
            destination = action.target_location
            if current_location is not None and destination == current_location:
                output_func(f'이미 {current_location}에 있다.')
                continue
            if destination in locations:
                return action
            output_func(f'이동할 수 없는 장소입니다. 가능한 장소: {location_text}')
            continue

        if action.action_type == 'travel' and action.target_settlement_id:
            if not travel_targets or action.target_settlement_id not in travel_targets:
                output_func(f'이동할 수 없는 정착지입니다. 가능한 정착지: {travel_text}')
                continue
            return action

        if action.action_type == 'talk' and action.target_npc_id:
            return action

        if action.action_type == 'wait':
            return action

        output_func('지원하지 않는 행동입니다. `wait`, `move <장소>`, `talk <대상>`, `travel <settlement>` 형식으로 입력하세요.')


if __name__ == '__main__':
    args = parse_args()
    run_simulation(ticks=args.ticks, mode=Mode(args.mode))
