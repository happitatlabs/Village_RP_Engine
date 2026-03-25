from __future__ import annotations

import argparse
import json
from collections import deque
from collections.abc import Callable

from village_rp_engine.config import DEFAULT_SIMULATION_TICKS
from village_rp_engine.core.mode_controller import build_world_engine, create_default_world_snapshot, run_mode_step
from village_rp_engine.core.world_engine import (
    can_travel_between_settlements,
    get_player_interaction_choices,
    load_world_state_from_slot,
    reset_world_to_seed,
    save_world_state_to_slot,
)
from village_rp_engine.input_aliases import parse_player_input
from village_rp_engine.logs.chronicle import (
    build_chronicle_query,
    build_world_summary_snapshot,
    compare_continents,
    compare_regions,
    compare_settlements,
    get_player_timeline,
)
from village_rp_engine.logs.world_log import format_tick_summary
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.phase1_world import WorldSnapshot
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
        if mode == Mode.RP:
            action: PlayerAction | None = None
            while True:
                settlement_definition = snapshot.settlement_definition
                locations = [location for location in settlement_definition.locations if location != '집']
                npc_ids = list(settlement_definition.npc_ids)
                travel_targets = [
                    settlement_id
                    for settlement_id in snapshot.settlement_definitions
                    if can_travel_between_settlements(snapshot.active_settlement_id, settlement_id, snapshot.settlement_links)
                ]
                prompt_result = prompt_player_action(
                    locations,
                    npc_ids,
                    current_location=snapshot.settlement_state.player_location,
                    travel_targets=travel_targets,
                    choice_ids=[choice['choice_id'] for choice in get_player_interaction_choices()],
                    history_snapshot=snapshot,
                    save_func=lambda slot, current_snapshot=snapshot: save_world_state_to_slot(current_snapshot, slot),
                    load_func=lambda slot: load_world_state_from_slot(
                        slot,
                        settlement_definitions=world_engine.settlement_definitions,
                        settlement_links=world_engine.settlement_links,
                        region_definitions=world_engine.region_definitions,
                        continent_definitions=world_engine.continent_definitions,
                    ),
                    reset_func=lambda: reset_world_to_seed(world_engine),
                )
                if isinstance(prompt_result, WorldSnapshot):
                    snapshot = prompt_result
                    continue
                if prompt_result is None:
                    continue
                action = prompt_result
                break
            snapshot = run_mode_step(world_engine, snapshot, mode, action_provider=lambda action=action: action)
        else:
            snapshot = run_mode_step(world_engine, snapshot, mode, action_provider=None)
        chronicle_query = build_chronicle_query(snapshot)
        world_summary = build_world_summary_snapshot(snapshot)
        player_history = get_player_timeline(snapshot, limit=4)
        print(f'[Settlement] {snapshot.active_settlement_id}')
        print(format_tick_summary(snapshot.settlement_state, mode=mode))
        print('최근 세계 변화:')
        for entry in chronicle_query.query_entries(limit=4).entries:
            print(f'- Day {entry.day} Tick {entry.tick} | {entry.text}')
        print('플레이어 기준 history:')
        for item in player_history:
            print(f'- {item.perspective}: {item.entry.text}')
        print(f'세계 요약 | Day {world_summary.day} Tick {world_summary.tick}')
        for line in [*world_summary.region_summaries[:2], *world_summary.continent_summaries[:1]]:
            print(f'- {line}')
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


def render_history_command(snapshot: WorldSnapshot, raw: str, output_func: Callable[[str], None]) -> bool:
    tokens = raw.strip().split()
    if not tokens or tokens[0] != 'history':
        return False

    query = build_chronicle_query(snapshot)
    if len(tokens) == 1 or tokens[1] == 'recent':
        result = query.query_entries(limit=5)
        output_func('최근 세계 변화:')
        for entry in result.entries:
            output_func(f'Day {entry.day} Tick {entry.tick} | {entry.category} | {entry.text}')
        return True

    if tokens[1] == 'settlement' and len(tokens) >= 3:
        result = query.query_entries(settlement_id=tokens[2], limit=5)
        output_func(f'settlement history: {tokens[2]}')
        for entry in result.entries:
            output_func(f'Day {entry.day} Tick {entry.tick} | {entry.category} | {entry.text}')
        return True

    if tokens[1] == 'region' and len(tokens) >= 3:
        result = query.query_entries(region_id=tokens[2], limit=5)
        output_func(f'region history: {tokens[2]}')
        for entry in result.entries:
            output_func(f'Day {entry.day} Tick {entry.tick} | {entry.category} | {entry.text}')
        return True

    if tokens[1] == 'continent' and len(tokens) >= 3:
        result = query.query_entries(continent_id=tokens[2], limit=5)
        output_func(f'continent history: {tokens[2]}')
        for entry in result.entries:
            output_func(f'Day {entry.day} Tick {entry.tick} | {entry.category} | {entry.text}')
        return True

    if tokens[1] == 'compare' and len(tokens) >= 4:
        scope_type = tokens[2]
        scope_ids = tokens[3:]
        if scope_type == 'settlement':
            result = compare_settlements(snapshot, scope_ids)
        elif scope_type == 'region':
            result = compare_regions(snapshot, scope_ids)
        elif scope_type == 'continent':
            result = compare_continents(snapshot, scope_ids)
        else:
            result = compare_settlements(snapshot, tokens[2:4])
            scope_type = 'settlement'
            scope_ids = tokens[2:4]
        output_func(f"comparison ({scope_type}): {' vs '.join(scope_ids)}")
        for line in result.summary_lines:
            output_func(line)
        return True

    output_func('history 명령: `history recent`, `history settlement <id>`, `history region <id>`, `history continent <id>`, `history compare settlement <a> <b>`, `history compare region <a> <b>`, `history compare continent <a> [b]`')
    return True


def prompt_player_action(
    locations: list[str],
    npc_ids: list[str],
    current_location: str | None,
    travel_targets: list[str] | None = None,
    choice_ids: list[str] | None = None,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
    history_snapshot: WorldSnapshot | None = None,
    save_func: Callable[[int], dict] | None = None,
    load_func: Callable[[int], WorldSnapshot] | None = None,
    reset_func: Callable[[], WorldSnapshot] | None = None,
) -> PlayerAction | WorldSnapshot | None:
    location_text = ', '.join(locations)
    npc_text = ', '.join(npc_ids)
    travel_text = ', '.join(travel_targets or [])
    choice_text = ', '.join(choice_ids or [])
    output_func(
        '행동 선택: `wait`, `move <장소>`, `talk <대상>`, `travel <settlement>`, `choose <선택>`, `history ...`, `save <1-3>`, `load <1-3>`, `reset` '
        f'(예: `이동 술집`, `대화 대장장이`, `travel village_2`, `choose follow_whisper`, `save 1`, `load 2`) ({location_text} | {npc_text} | {travel_text} | {choice_text})'
    )
    while True:
        try:
            raw = input_func('> ')
        except EOFError:
            return PlayerAction.wait()

        save_tokens = raw.strip().split()
        if save_tokens and save_tokens[0] == 'save':
            if save_func is None:
                output_func('save를 사용할 수 없습니다.')
            elif len(save_tokens) != 2 or not save_tokens[1].isdigit():
                output_func('save 사용법: `save <1-3>`')
            else:
                try:
                    result = save_func(int(save_tokens[1]))
                except Exception:
                    output_func('save 실패: 유효한 슬롯(1-3)이 필요하다.')
                else:
                    output_func(json.dumps(result, ensure_ascii=False))
                    return history_snapshot
            continue

        if raw.strip() == 'reset':
            if reset_func is None:
                output_func('reset을 사용할 수 없습니다.')
            else:
                snapshot = reset_func()
                output_func('world reset complete')
                return snapshot
            continue

        load_tokens = raw.strip().split()
        if load_tokens and load_tokens[0] == 'load':
            if load_func is None:
                output_func('load를 사용할 수 없습니다.')
            elif len(load_tokens) != 2 or not load_tokens[1].isdigit():
                output_func('load 사용법: `load <1-3>`')
            else:
                try:
                    snapshot = load_func(int(load_tokens[1]))
                except Exception:
                    output_func('load 실패: 유효한 저장 슬롯(1-3)이 필요하다.')
                else:
                    output_func('world load complete')
                    return snapshot
            continue

        if raw.strip().startswith('history'):
            if history_snapshot is None:
                output_func('history 조회를 사용할 수 없습니다.')
            else:
                render_history_command(history_snapshot, raw, output_func)
            continue

        action = parse_player_input(raw)
        if action is None:
            output_func('지원하지 않는 행동입니다. `wait`, `move <장소>`, `talk <대상>`, `travel <settlement>`, `choose <선택>` 형식으로 입력하세요.')
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

        if action.action_type == 'choose' and action.choice_id:
            if not choice_ids or action.choice_id not in choice_ids:
                output_func(f'지원하지 않는 선택입니다. 가능한 선택: {choice_text}')
                continue
            return action

        if action.action_type == 'wait':
            return action

        output_func('지원하지 않는 행동입니다. `wait`, `move <장소>`, `talk <대상>`, `travel <settlement>`, `choose <선택>` 형식으로 입력하세요.')


if __name__ == '__main__':
    args = parse_args()
    run_simulation(ticks=args.ticks, mode=Mode(args.mode))
