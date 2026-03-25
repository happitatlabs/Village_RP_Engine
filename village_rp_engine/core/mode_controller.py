from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from village_rp_engine.config import DEFAULT_PLAYER_LOCATION, DEFAULT_RANDOM_SEED, MEDIATE_TAVERN_CONFLICT_QUEST_ID
from village_rp_engine.core.tick_engine import TickEngine
from village_rp_engine.core.world_engine import Phase1WorldEngine, build_world_snapshot
from village_rp_engine.core.world_state import WorldState, create_initial_world_state
from village_rp_engine.domain.settlement_data import (
    build_npcs_for_settlement,
    build_phase1_settlement,
    build_phase2_settlement_links,
    build_phase2_settlements,
)
from village_rp_engine.models.mode import Mode
from village_rp_engine.models.phase1_world import SettlementDefinition, WorldSnapshot
from village_rp_engine.models.player_action import PlayerAction
from village_rp_engine.systems.player_progress_system import PlayerProgressSystem


PLAYER_PROGRESS_SYSTEM = PlayerProgressSystem()


def build_engine() -> TickEngine:
    settlement = build_phase1_settlement()
    return build_tick_engine_from_settlement(settlement)


def build_tick_engine_from_settlement(settlement: SettlementDefinition) -> TickEngine:
    return TickEngine(
        npcs=build_npcs_for_settlement(settlement),
        schedules={npc_id: dict(schedule) for npc_id, schedule in settlement.schedules.items()},
        event_definitions=list(settlement.event_definitions),
        seed=DEFAULT_RANDOM_SEED,
    )


def build_world_engine() -> Phase1WorldEngine:
    settlements = build_phase2_settlements()
    settlement_engines = {
        settlement_id: build_tick_engine_from_settlement(settlement)
        for settlement_id, settlement in settlements.items()
    }
    return Phase1WorldEngine(
        settlement_definitions=settlements,
        settlement_engines=settlement_engines,
        settlement_links=build_phase2_settlement_links(),
    )


def create_state_from_settlement(
    settlement: SettlementDefinition,
    player_location: str | None = DEFAULT_PLAYER_LOCATION,
) -> WorldState:
    state = create_initial_world_state(player_location=player_location)
    state.settlement_id = settlement.settlement_id
    state.security = settlement.security.base_value
    state.stress = settlement.stress_default
    state.economy_profile = dict(settlement.economy_profile.values)
    state.npc_locations = {
        npc_id: schedule[state.time_phase]
        for npc_id, schedule in settlement.schedules.items()
    }
    state.previous_npc_locations = dict(state.npc_locations)
    PLAYER_PROGRESS_SYSTEM.ensure_initialized(state)
    state.quest_status.setdefault(MEDIATE_TAVERN_CONFLICT_QUEST_ID, 'not_started')
    return state


def create_default_state() -> WorldState:
    state = create_state_from_settlement(build_phase1_settlement(), player_location=DEFAULT_PLAYER_LOCATION)
    PLAYER_PROGRESS_SYSTEM.ensure_initialized(state)
    state.quest_status.setdefault(MEDIATE_TAVERN_CONFLICT_QUEST_ID, 'not_started')
    return state


def create_default_world_snapshot() -> WorldSnapshot:
    settlements = build_phase2_settlements()
    states = {
        settlement_id: create_state_from_settlement(
            settlement,
            player_location=DEFAULT_PLAYER_LOCATION if settlement_id == 'village_1' else None,
        )
        for settlement_id, settlement in settlements.items()
    }
    return build_world_snapshot(
        settlement_definitions=settlements,
        settlement_states=states,
        active_settlement_id='village_1',
        recently_visited_ids=(),
        settlement_links=build_phase2_settlement_links(),
    )


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
        raise ValueError('RP mode requires an action provider.')

    action = action_provider()
    if action.action_type == 'talk':
        return run_mode_talk(engine, state, action)

    next_state = engine.run_tick(state, player_action=action)
    PLAYER_PROGRESS_SYSTEM.refresh_after_tick(next_state)
    return next_state


def run_mode_step(
    world_engine: Phase1WorldEngine,
    snapshot: WorldSnapshot,
    mode: Mode,
    action_provider: Callable[[], PlayerAction] | None = None,
) -> WorldSnapshot:
    action = None if action_provider is None else action_provider()
    return world_engine.run_step(snapshot, mode, action=action)


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
