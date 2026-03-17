from __future__ import annotations

from collections.abc import Iterable

from village_rp_engine.core.mode_controller import create_default_state
from village_rp_engine.core.world_state import WorldState
from village_rp_engine.input_aliases import parse_player_input
from village_rp_engine.models.npc_state import NPCRecentState
from village_rp_engine.models.player_action import PlayerAction


DEFAULT_DEMO_COMMANDS = [
    "move 대장간",
    "대화 대장장이",
    "이동 술집",
    "talk innkeeper",
    "wait",
    "광장 가기",
    "경비대장 대화",
]

GUARD_DAWN_DEMO_COMMANDS = [
    "wait",
    "경비대장 대화",
]

ELDER_MEDIATION_DEMO_COMMANDS = [
    "촌장 말걸기",
]

FLOW_DEMO_DESCRIPTION = "이 데모는 실제 흐름(사건 -> 상태 -> 후속 반응)을 따라가며 엔진의 통합 동작을 검증한다."
GUARD_DAWN_DEMO_DESCRIPTION = "주의: 이 데모는 새벽 직전 위치 조건을 사전 주입해 경비대장의 outsider 반응만 짧게 검증한다."
ELDER_MEDIATION_DEMO_DESCRIPTION = "주의: 이 데모는 farmer complaint recent state를 사전 주입해 촌장의 간접 반응만 짧게 검증한다."


class DemoActionProvider:
    def __init__(self, actions: Iterable[PlayerAction]) -> None:
        self.actions = list(actions)
        self.index = 0

    def next_action(self) -> PlayerAction:
        if self.index >= len(self.actions):
            return PlayerAction.wait()

        action = self.actions[self.index]
        self.index += 1
        return action


def build_demo_actions(commands: Iterable[str] | None = None) -> list[PlayerAction]:
    return [parse_demo_action(command) for command in (commands or DEFAULT_DEMO_COMMANDS)]


def build_guard_dawn_demo_actions() -> list[PlayerAction]:
    return build_demo_actions(GUARD_DAWN_DEMO_COMMANDS)


def build_elder_mediation_demo_actions() -> list[PlayerAction]:
    return build_demo_actions(ELDER_MEDIATION_DEMO_COMMANDS)


def create_guard_dawn_demo_state() -> WorldState:
    state = create_default_state()
    state.player_location = "광장"
    state.time_phase = "밤"
    state.npc_locations = {
        "blacksmith": "집",
        "farmer": "집",
        "innkeeper": "술집",
        "village_elder": "집",
        "guard_captain": "광장",
    }
    return state


def create_elder_mediation_demo_state() -> WorldState:
    state = create_default_state()
    state.player_location = "광장"
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
    return state


def parse_demo_action(command: str) -> PlayerAction:
    action = parse_player_input(command)
    if action is None:
        raise ValueError(f"지원하지 않는 데모 액션: {command}")
    return action


def format_action(action: PlayerAction) -> str:
    if action.action_type == "move" and action.target_location:
        return f"move {action.target_location}"
    if action.action_type == "talk" and action.target_npc_id:
        return f"talk {action.target_npc_id}"
    return "wait"


def print_demo_header(title: str, demo_kind: str, description: str, player_location: str) -> None:
    print(f"=== {title} ===")
    print(f"Demo Type: {demo_kind}")
    print(description)
    print(f"초기 플레이어 위치: {player_location}")
    print()
