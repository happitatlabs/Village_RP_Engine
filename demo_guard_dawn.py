from __future__ import annotations

from village_rp_engine.core.mode_controller import build_engine, run_mode_tick
from village_rp_engine.demo import (
    DemoActionProvider,
    GUARD_DAWN_DEMO_DESCRIPTION,
    build_guard_dawn_demo_actions,
    create_guard_dawn_demo_state,
    format_action,
    print_demo_header,
)
from village_rp_engine.logs.world_log import format_tick_summary
from village_rp_engine.main import get_mode_display_label
from village_rp_engine.models.mode import Mode


def run_demo() -> None:
    engine = build_engine()
    state = create_guard_dawn_demo_state()
    provider = DemoActionProvider(build_guard_dawn_demo_actions())

    print_demo_header(
        title=f"Village RP Engine | {get_mode_display_label(Mode.RP)} Guard Dawn Injection Demo",
        demo_kind="injection",
        description=GUARD_DAWN_DEMO_DESCRIPTION,
        player_location=state.player_location,
    )

    for _ in range(2):
        action = provider.next_action()
        print(f"Action: {format_action(action)}")
        state = run_mode_tick(engine, state, Mode.RP, action_provider=lambda action=action: action)
        print(format_tick_summary(state, mode=Mode.RP))
        print()


if __name__ == "__main__":
    run_demo()
