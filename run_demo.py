from __future__ import annotations

import argparse

from village_rp_engine.core.mode_controller import build_world_engine, create_default_world_snapshot, run_mode_step
from village_rp_engine.demo import (
    DemoActionProvider,
    FLOW_DEMO_DESCRIPTION,
    build_demo_actions,
    format_action,
    print_demo_header,
)
from village_rp_engine.logs.world_log import format_tick_summary
from village_rp_engine.main import get_mode_display_label
from village_rp_engine.models.mode import Mode


DEFAULT_DEMO_TICKS = 20


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Village RP Engine demo runner')
    parser.add_argument(
        '--ticks',
        type=int,
        default=DEFAULT_DEMO_TICKS,
        help='실행할 tick 수',
    )
    return parser.parse_args()


def run_demo(ticks: int = DEFAULT_DEMO_TICKS) -> None:
    world_engine = build_world_engine()
    snapshot = create_default_world_snapshot()
    provider = DemoActionProvider(build_demo_actions())

    print_demo_header(
        title=f'Village RP Engine | {get_mode_display_label(Mode.RP)} Flow Demo',
        demo_kind='flow',
        description=FLOW_DEMO_DESCRIPTION,
        player_location=snapshot.settlement_state.player_location,
    )

    for _ in range(ticks):
        action = provider.next_action()
        print(f'Action: {format_action(action)}')
        snapshot = run_mode_step(world_engine, snapshot, Mode.RP, action_provider=lambda action=action: action)
        print(format_tick_summary(snapshot.settlement_state, mode=Mode.RP))
        print()


if __name__ == '__main__':
    args = parse_args()
    run_demo(ticks=args.ticks)
