from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from village_rp_engine.config import DEFAULT_PLAYER_LOCATION, DEFAULT_RANDOM_SEED, MEDIATE_TAVERN_CONFLICT_QUEST_ID
from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_state import WorldState, create_initial_world_state
from village_rp_engine.domain.event_data import build_event_definitions
from village_rp_engine.domain.npc_data import build_npcs
from village_rp_engine.domain.schedule_data import build_schedules
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.systems.player_progress_system import PlayerProgressSystem


PLAYER_PROGRESS_SYSTEM = PlayerProgressSystem()


def build_engine() -> TickEngine:
    return TickEngine(
        npcs=build_npcs(),
        schedules=build_schedules(),
        event_definitions=build_event_definitions(),
        seed=DEFAULT_RANDOM_SEED,
    )


def create_default_state() -> WorldState:
    state = create_initial_world_state(player_location=DEFAULT_PLAYER_LOCATION)
    PLAYER_PROGRESS_SYSTEM.ensure_initialized(state)
    state.quest_status.setdefault(MEDIATE_TAVERN_CONFLICT_QUEST_ID, "not_started")
    return state


def run_mode_tick(
    engine: TickEngine,
    state: WorldState,
    mode: Mode,
    action_provider: Callable[[], PlayerAction] | None = None,
) -> WorldState:
    PLAYER_PROGRESS_SYSTEM.ensure_initialized(state)

    if mode == Mode.OBSERVER:
        next_state = engine.run_tick(state)
        PLAYER_PROGRESS_SYSTEM.refresh_after_tick(next_state)
        return next_state

    if action_provider is None:
        raise ValueError("RP mode requires an action provider.")

    action = action_provider()
    if action.action_type == "talk":
        return run_mode_talk(engine, state, action)

    next_state = engine.run_tick(state, player_action=action)
    PLAYER_PROGRESS_SYSTEM.refresh_after_tick(next_state)
    return next_state


def run_mode_talk(engine: TickEngine, state: WorldState, action: PlayerAction) -> WorldState:
    interaction_state = replace(
        state,
        dialogues=[],
        world_log=list(state.world_log),
        player_relationships=dict(state.player_relationships),
        quest_status=dict(state.quest_status),
        quest_contacts={quest_id: set(contacts) for quest_id, contacts in state.quest_contacts.items()},
    )
    engine.player_action_system.apply_action(interaction_state, action)
    target_npc_id = engine.dialogue_system.prepare_dialogue_target(interaction_state, action)
    interaction_state.dialogues = engine.dialogue_system.resolve_dialogue(interaction_state, target_npc_id, [])
    PLAYER_PROGRESS_SYSTEM.handle_player_talk(interaction_state, target_npc_id)
    return interaction_state
